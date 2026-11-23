// SPDX-License-Identifier: GPL-2.0
/*
 * SM-T575 E8D: START/STOP abort-latch concurrency test, HARD OFF ONLY.
 * No code path asserts the TAS2562 shutdown GPIO or writes TAS2562 I2C.
 * simulate_activation=1 authorizes ONLY a sleeping mock work item.
 */
#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/atomic.h>
#include <linux/workqueue.h>
#include <linux/delay.h>
#include <linux/spinlock.h>
#include <linux/pm.h>
#include <linux/of.h>
#include <sound/soc.h>
#include <sound/pcm.h>

static bool simulate_activation;
module_param(simulate_activation, bool, 0400);
MODULE_PARM_DESC(simulate_activation,
                 "Run abortable mock init on first PCM START; no hardware activation");

static DEFINE_SPINLOCK(e8d_lock);
static atomic_t e8d_running = ATOMIC_INIT(0);
static atomic_t e8d_aborted = ATOMIC_INIT(0);
static atomic_t e8d_attempted = ATOMIC_INIT(0);
static struct gpio_desc *e8d_sdz;
static struct device *e8d_dev;

static void e8d_gpio_off(void)
{
    unsigned long flags;

    spin_lock_irqsave(&e8d_lock, flags);
    if (e8d_sdz)
        gpiod_set_value(e8d_sdz, 0);
    spin_unlock_irqrestore(&e8d_lock, flags);
}

static void e8d_fake_init(struct work_struct *work);
static DECLARE_WORK(e8d_work, e8d_fake_init);

static void e8d_fake_init(struct work_struct *work)
{
    int i;

    dev_info(e8d_dev, "E8D: mock initialization BEGIN; amplifier OFF\n");
    for (i = 0; i < 20; i++) {
        if (atomic_read(&e8d_aborted) || !atomic_read(&e8d_running)) {
            e8d_gpio_off();
            dev_info(e8d_dev, "E8D: mock initialization ABORTED; amplifier OFF\n");
            return;
        }
        msleep(25);
    }

    e8d_gpio_off();
    dev_info(e8d_dev,
             "E8D: mock initialization FINISHED; amplifier OFF\n");
}

static int e8d_pcm_startup(struct snd_pcm_substream *substream,
                          struct snd_soc_dai *dai)
{
    if (!e8d_sdz)
        return -ENODEV;
    e8d_gpio_off();
    return 0;
}

static int e8d_pcm_trigger(struct snd_pcm_substream *substream, int cmd,
                           struct snd_soc_dai *dai)
{
    unsigned long flags;
    bool denied;

    switch (cmd) {
    case SNDRV_PCM_TRIGGER_START:
    case SNDRV_PCM_TRIGGER_RESUME:
    case SNDRV_PCM_TRIGGER_PAUSE_RELEASE:
        spin_lock_irqsave(&e8d_lock, flags);
        denied = !!atomic_read(&e8d_aborted);
        atomic_set(&e8d_running, 1);
        spin_unlock_irqrestore(&e8d_lock, flags);

        if (denied) {
            dev_info(dai->dev,
                     "E8D: second START DENIED by abort latch; amplifier OFF\n");
        } else if (simulate_activation &&
                   atomic_cmpxchg(&e8d_attempted, 0, 1) == 0) {
            schedule_work(&e8d_work);
        }
        return 0;

    case SNDRV_PCM_TRIGGER_STOP:
    case SNDRV_PCM_TRIGGER_SUSPEND:
    case SNDRV_PCM_TRIGGER_PAUSE_PUSH:
        spin_lock_irqsave(&e8d_lock, flags);
        atomic_set(&e8d_aborted, 1);
        atomic_set(&e8d_running, 0);
        gpiod_set_value(e8d_sdz, 0);
        spin_unlock_irqrestore(&e8d_lock, flags);
        dev_info(dai->dev, "E8D: STOP latched; amplifier OFF\n");
        return 0;
    default:
        return -EINVAL;
    }
}

static void e8d_pcm_shutdown(struct snd_pcm_substream *substream,
                             struct snd_soc_dai *dai)
{
    atomic_set(&e8d_aborted, 1);
    atomic_set(&e8d_running, 0);
    e8d_gpio_off();
    cancel_work_sync(&e8d_work);
    e8d_gpio_off();
    dev_info(dai->dev, "E8D: PCM closed; amplifier OFF\n");
}

static const struct snd_soc_dai_ops e8d_dai_ops = {
    .startup = e8d_pcm_startup,
    .trigger = e8d_pcm_trigger,
    .shutdown = e8d_pcm_shutdown,
};

static struct snd_soc_dai_driver e8d_dai = {
    .name = "tas2562-safeactive",
    .playback = {
        .stream_name = "Playback",
        .channels_min = 2,
        .channels_max = 2,
        .rates = SNDRV_PCM_RATE_48000,
        .formats = SNDRV_PCM_FMTBIT_S32_LE,
    },
    .ops = &e8d_dai_ops,
};

static const struct snd_soc_dapm_widget e8d_widgets[] = {
    SND_SOC_DAPM_OUTPUT("OUT"),
};

static const struct snd_soc_component_driver e8d_component = {
    .name = "tas2562-safeactive",
    .dapm_widgets = e8d_widgets,
    .num_dapm_widgets = ARRAY_SIZE(e8d_widgets),
};

static int e8d_probe(struct i2c_client *client)
{
    struct gpio_desc *sdz;
    int ret;

    if (client->addr != 0x4c)
        return -ENODEV;

    sdz = devm_gpiod_get(&client->dev, "shutdown", GPIOD_OUT_LOW);
    if (IS_ERR(sdz))
        return PTR_ERR(sdz);
    if (gpiod_is_active_low(sdz) || gpiod_cansleep(sdz))
        return -EOPNOTSUPP;

    e8d_sdz = sdz;
    e8d_dev = &client->dev;
    atomic_set(&e8d_running, 0);
    atomic_set(&e8d_aborted, 0);
    atomic_set(&e8d_attempted, 0);

    ret = devm_snd_soc_register_component(&client->dev,
                                           &e8d_component, &e8d_dai, 1);
    if (ret) {
        e8d_gpio_off();
        e8d_sdz = NULL;
        e8d_dev = NULL;
        return ret;
    }
    dev_info(&client->dev,
             "E8D: simulation-only TAS2562 transport ready; SDZ LOW\n");
    return 0;
}

static void e8d_remove(struct i2c_client *client)
{
    atomic_set(&e8d_aborted, 1);
    atomic_set(&e8d_running, 0);
    e8d_gpio_off();
    cancel_work_sync(&e8d_work);
    e8d_gpio_off();
    e8d_sdz = NULL;
    e8d_dev = NULL;
}

static int e8d_suspend(struct device *dev)
{
    atomic_set(&e8d_aborted, 1);
    atomic_set(&e8d_running, 0);
    e8d_gpio_off();
    cancel_work_sync(&e8d_work);
    e8d_gpio_off();
    return 0;
}

static int e8d_resume(struct device *dev)
{
    e8d_gpio_off();
    return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(e8d_pm_ops, e8d_suspend, e8d_resume);

static const struct of_device_id e8d_of_match[] = {
    { .compatible = "samsung,t575-tas2562-safeactive" },
    { }
};
MODULE_DEVICE_TABLE(of, e8d_of_match);

static struct i2c_driver e8d_driver = {
    .driver = {
        .name = "t575-tas2562-safeactive",
        .of_match_table = e8d_of_match,
        .pm = pm_sleep_ptr(&e8d_pm_ops),
    },
    .probe = e8d_probe,
    .remove = e8d_remove,
    .shutdown = e8d_remove,
};

module_i2c_driver(e8d_driver);

MODULE_DESCRIPTION("SM-T575 E8D mock in-flight STOP test; TAS2562 always OFF");
MODULE_LICENSE("GPL");
