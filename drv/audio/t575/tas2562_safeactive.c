// SPDX-License-Identifier: GPL-2.0
/*
 * SM-T575 Stage E4D 64-clock silent transport.
 * Registers an ASoC DAI with the amplifier held in shutdown.
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/of.h>
#include <linux/delay.h>
#include <linux/mutex.h>
#include <linux/sysfs.h>
#include <linux/pm.h>
#include <linux/hrtimer.h>
#include <linux/ktime.h>
#include <linux/jiffies.h>
#include <linux/atomic.h>
#include <sound/soc.h>
#include <sound/pcm.h>


#define TAS_PAGE       0x00
#define TAS_BOOK       0x7f
#define TAS_POWER      0x02
#define TAS_REVISION   0x7d
#define TAS_TDM_DET    0x11
#define TAS_LIVE0      0x1f
#define TAS_LIVE1      0x20
#define TAS_LATCH0     0x24
#define TAS_LATCH1     0x25


#define TAS_GAIN       0x03
#define TAS_GAIN_MASK  0x3e
#define TAS_DVC_PAGE   0x02
#define TAS_DVC_FIRST  0x0c
#define TAS_MISC       0x04
#define TAS_TDM_CFG2   0x08
#define TAS_RETRY_MASK 0x30

static int t575_configure_shutdown(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    static const u8 attenuation[] = {
        0x00, 0x10, 0x62, 0x4e
    };
    int ret, value, target, i;

    /* Confirm software shutdown before configuration. */
    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0)
        return value;

    if (value != 0x0e)
        return -EIO;

    /* Preserve every bit outside the gain field. */
    value = i2c_smbus_read_byte_data(client, TAS_GAIN);
    if (value < 0)
        return value;

    target = value & ~TAS_GAIN_MASK;

    dev_info(dev, "GAIN before=0x%02x target=0x%02x\n",
             value, target);

    ret = i2c_smbus_write_byte_data(client, TAS_GAIN, target);
    if (ret < 0)
        return ret;

    value = i2c_smbus_read_byte_data(client, TAS_GAIN);
    if (value < 0)
        return value;

    if (value != target)
        return -EIO;

    dev_info(dev, "PASS: minimum gain readback 0x%02x\n",
             value);

    ret = i2c_smbus_write_byte_data(client,
                                    TAS_PAGE, TAS_DVC_PAGE);
    if (ret < 0)
        return ret;

    /* Read original coefficient without changing it. */
    for (i = 0; i < ARRAY_SIZE(attenuation); i++) {
        value = i2c_smbus_read_byte_data(
                    client, TAS_DVC_FIRST + i);
        if (value < 0)
            return value;

        dev_info(dev, "DVC before 0x%02x = 0x%02x\n",
                 TAS_DVC_FIRST + i, value);
    }

    /* MSB first; LSB last. */
    for (i = 0; i < ARRAY_SIZE(attenuation); i++) {
        ret = i2c_smbus_write_byte_data(
                  client, TAS_DVC_FIRST + i,
                  attenuation[i]);

        if (ret < 0)
            return ret;
    }

    for (i = 0; i < ARRAY_SIZE(attenuation); i++) {
        value = i2c_smbus_read_byte_data(
                    client, TAS_DVC_FIRST + i);

        if (value < 0)
            return value;

        if (value != attenuation[i])
            return -EIO;

        dev_info(dev, "DVC verified 0x%02x = 0x%02x\n",
                 TAS_DVC_FIRST + i, value);
    }

    ret = i2c_smbus_write_byte_data(client, TAS_PAGE, 0);
    if (ret < 0)
        return ret;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0)
        return value;

    if (value != 0x0e)
        return -EIO;

    dev_info(dev, "PASS: -60 dB coefficient verified\n");
    dev_info(dev, "PASS: software shutdown preserved\n");

    return 0;
}



#define TAS_MISC2       0x05
#define TAS_INT_CLK     0x30
#define E4D_TEST_MS     500
#define E4D_WATCHDOG_MS 750

struct e4d_watchdog {
    struct hrtimer timer;
    struct gpio_desc *sdz;
    atomic_t expired;
};

static bool e4d_activation_used;
static bool allow_activation;

module_param(allow_activation, bool, 0400);
MODULE_PARM_DESC(allow_activation,
    "Permit restricted E4D activation diagnostics (default: false)");


static enum hrtimer_restart e4d_watchdog_stop(struct hrtimer *timer)
{
    struct e4d_watchdog *wd =
        container_of(timer, struct e4d_watchdog, timer);

    gpiod_set_value(wd->sdz, 0);
    atomic_set(&wd->expired, 1);

    return HRTIMER_NORESTART;
}

static int e4d_update_verified(
    struct i2c_client *client,
    u8 reg, u8 mask, u8 bits)
{
    int value, target, ret;

    value = i2c_smbus_read_byte_data(client, reg);
    if (value < 0)
        return value;

    target = (value & ~mask) | (bits & mask);

    ret = i2c_smbus_write_byte_data(client, reg, target);
    if (ret < 0)
        return ret;

    value = i2c_smbus_read_byte_data(client, reg);
    if (value < 0)
        return value;

    return value == target ? 0 : -EIO;
}

static int e4d_monitor(struct i2c_client *client)
{
    static const u8 fault_regs[] = {
        TAS_LIVE0, TAS_LIVE1, TAS_LATCH0, TAS_LATCH1
    };
    int i, value;

    for (i = 0; i < ARRAY_SIZE(fault_regs); i++) {
        value = i2c_smbus_read_byte_data(client, fault_regs[i]);

        if (value < 0)
            return value;

        if (value) {
            dev_err(&client->dev,
                "E4D: fault register %02x = %02x\n",
                fault_regs[i], value);
            return -EIO;
        }
    }

    value = i2c_smbus_read_byte_data(client, TAS_TDM_DET);

    if (value < 0)
        return value;

    if ((value & 0x7f) != 0x24)
        return -EIO;

    return 0;
}

static int e4d_play_test(
    struct i2c_client *client,
    struct gpio_desc *sdz)
{
    struct device *dev = &client->dev;
    struct e4d_watchdog wd;
    unsigned long deadline;
    int ret, value;
    unsigned int samples = 0;

    /* Immediate hardware shutdown. */
    ret = e4d_update_verified(client, TAS_MISC2, 0xc0, 0x40);
    if (ret)
        return ret;

    /* Disable optional clock-dependent power control. */
    ret = e4d_update_verified(client, TAS_INT_CLK, 0x80, 0);
    if (ret)
        return ret;

    /* Confirm configuration and valid clocks before activation. */
    ret = e4d_monitor(client);
    if (ret)
        return ret;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value != 0x0e)
        return value < 0 ? value : -EIO;

    wd.sdz = sdz;
    atomic_set(&wd.expired, 0);

    if (gpiod_cansleep(sdz))
        return -EOPNOTSUPP;

    hrtimer_init(&wd.timer, CLOCK_MONOTONIC, HRTIMER_MODE_REL);
    wd.timer.function = e4d_watchdog_stop;

    hrtimer_start(&wd.timer,
                  ms_to_ktime(E4D_WATCHDOG_MS),
                  HRTIMER_MODE_REL);

    deadline = jiffies + msecs_to_jiffies(E4D_TEST_MS);

    /*
     * Preserve disabled current and voltage sense paths.
     * Only change MODE from software shutdown to active.
     */
    if (atomic_read(&wd.expired) ||
        !hrtimer_active(&wd.timer)) {
        ret = -ETIMEDOUT;
        goto stop;
    }

    ret = i2c_smbus_write_byte_data(client, TAS_POWER, 0x0c);
    if (ret < 0)
        goto stop;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value != 0x0c) {
        ret = value < 0 ? value : -EIO;
        goto stop;
    }

    dev_info(dev, "E4D: bounded active test started\n");

    while (time_before(jiffies, deadline)) {
        if (atomic_read(&wd.expired)) {
            ret = -ETIMEDOUT;
            goto stop;
        }

        ret = e4d_monitor(client);
        if (ret)
            goto stop;

        value = i2c_smbus_read_byte_data(client, TAS_POWER);

        if (value != 0x0c) {
            ret = value < 0 ? value : -EIO;
            goto stop;
        }

        samples++;
        msleep(5);
    }

    ret = samples ? 0 : -ETIMEDOUT;

stop:
    gpiod_set_value_cansleep(sdz, 0);

    hrtimer_cancel(&wd.timer);

    if (atomic_read(&wd.expired))
        ret = -ETIMEDOUT;

    if (ret)
        dev_err(dev, "E4D: activation aborted: %d\n", ret);
    else
        dev_info(dev, "E4D: bounded active test completed\n");

    return ret;
}

static DEFINE_MUTEX(safeactive_lock);

static bool safeactive_suspended;

static ssize_t safeactive_store(
    struct device *dev,
    struct device_attribute *attr,
    const char *buf, size_t count)
{
    struct i2c_client *client = to_i2c_client(dev);
    struct gpio_desc *sdz = i2c_get_clientdata(client);
    int ret, value, i;
    int det, live0, live1, latch0, latch1;
    int matches = 0;
    bool activate;

    if (!sdz)
        return -ENODEV;

    activate = sysfs_streq(buf, "play-test");

    if (activate && !allow_activation)
        return -EPERM;

    if (!activate && !sysfs_streq(buf, "check"))
        return -EINVAL;

    mutex_lock(&safeactive_lock);

    if (safeactive_suspended ||
        (activate && e4d_activation_used)) {
        mutex_unlock(&safeactive_lock);
        return -EBUSY;
    }

    gpiod_set_value_cansleep(sdz, 0);
    usleep_range(10000, 12000);

    gpiod_set_value_cansleep(sdz, 1);
    usleep_range(5000, 6000);

    ret = i2c_smbus_write_byte_data(client, TAS_PAGE, 0);
    if (ret < 0)
        goto out;

    ret = i2c_smbus_write_byte_data(client, TAS_BOOK, 0);
    if (ret < 0)
        goto out;

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value < 0) {
        ret = value;
        goto out;
    }

    if (value != 0x0e) {
        ret = -EIO;
        goto out;
    }

    value = i2c_smbus_read_byte_data(client, TAS_REVISION);
    if (value < 0) {
        ret = value;
        goto out;
    }

    if (value != 0x10) {
        ret = -ENODEV;
        goto out;
    }


    /* Reapply E2 gain and digital attenuation. */
    ret = t575_configure_shutdown(client);
    if (ret)
        goto out;

    /* Disable automatic overcurrent/temperature retries. */
    value = i2c_smbus_read_byte_data(client, TAS_MISC);
    if (value < 0) {
        ret = value;
        goto out;
    }

    value &= ~TAS_RETRY_MASK;

    ret = i2c_smbus_write_byte_data(client, TAS_MISC, value);
    if (ret < 0)
        goto out;

    ret = i2c_smbus_read_byte_data(client, TAS_MISC);
    if (ret < 0)
        goto out;

    if (ret != value) {
        ret = -EIO;
        goto out;
    }

    dev_info(dev, "E4D: automatic fault retries disabled\n");

    /* Configure 32-bit receive words in 32-bit slots. */
    value = i2c_smbus_read_byte_data(client, TAS_TDM_CFG2);
    if (value < 0) {
        ret = value;
        goto out;
    }

    value = (value & ~0x0f) | 0x0e;

    ret = i2c_smbus_write_byte_data(client, TAS_TDM_CFG2, value);
    if (ret < 0)
        goto out;

    ret = i2c_smbus_read_byte_data(client, TAS_TDM_CFG2);
    if (ret < 0)
        goto out;

    if (ret != value) {
        ret = -EIO;
        goto out;
    }

    dev_info(dev, "E4D: TDM_CFG2 verified: %02x\n", value);

    value = i2c_smbus_read_byte_data(client, TAS_POWER);
    if (value != 0x0e) {
        ret = value < 0 ? value : -EIO;
        goto out;
    }

    for (i = 0; i < 10; i++) {
        value = i2c_smbus_read_byte_data(client, TAS_POWER);

        if (value != 0x0e) {
            ret = value < 0 ? value : -EIO;
            goto out;
        }

        det = i2c_smbus_read_byte_data(client, TAS_TDM_DET);
        live0 = i2c_smbus_read_byte_data(client, TAS_LIVE0);
        live1 = i2c_smbus_read_byte_data(client, TAS_LIVE1);
        latch0 = i2c_smbus_read_byte_data(client, TAS_LATCH0);
        latch1 = i2c_smbus_read_byte_data(client, TAS_LATCH1);

        if (det < 0 || live0 < 0 || live1 < 0 ||
            latch0 < 0 || latch1 < 0) {
            ret = -EIO;
            goto out;
        }

        dev_info(dev,
            "E4D sample %d: DET=%02x ratio=%x rate=%x live=%02x/%02x latch=%02x/%02x\n",
            i, det, (det >> 3) & 0xf, det & 7,
            live0, live1, latch0, latch1);

        if (live0 || live1 || latch0 || latch1) {
            ret = -EIO;
            goto out;
        }

        if ((det & 0x7f) == 0x24)
            matches++;

        msleep(20);
    }

    value = i2c_smbus_read_byte_data(client, TAS_POWER);

    if (value != 0x0e) {
        ret = value < 0 ? value : -EIO;
        goto out;
    }

    dev_info(dev,
        "E4D: clock matches %d/10; software shutdown verified\n",
        matches);

    if (matches != 10) {
        ret = -EAGAIN;
        goto out;
    }

    if (activate) {
        e4d_activation_used = true;

        ret = e4d_play_test(client, sdz);
        if (ret)
            goto out;
    }

    ret = count;

out:
    gpiod_set_value_cansleep(sdz, 0);
    dev_info(dev, "E4D: hardware shutdown restored\n");

    mutex_unlock(&safeactive_lock);

    return ret;
}

static DEVICE_ATTR(safeactive, 0200, NULL, safeactive_store);

static int t575_safeactive_startup(
    struct snd_pcm_substream *substream,
    struct snd_soc_dai *dai)
{
    struct gpio_desc *sdz = dev_get_drvdata(dai->dev);

    if (!sdz)
        return -ENODEV;

    mutex_lock(&safeactive_lock);
    gpiod_set_value_cansleep(sdz, 0);
    mutex_unlock(&safeactive_lock);

    dev_info(dai->dev,
             "E4D: silent PCM transport; amplifier remains disabled\n");
    return 0;
}

static const struct snd_soc_dai_ops t575_safeactive_ops = {
    .startup = t575_safeactive_startup,
};

static struct snd_soc_dai_driver t575_safeactive_dai = {
    .name = "tas2562-safeactive",
    .playback = {
        .stream_name = "Playback",
        .channels_min = 2,
        .channels_max = 2,
        .rates = SNDRV_PCM_RATE_48000,
        .formats = SNDRV_PCM_FMTBIT_S32_LE,
    },
    .ops = &t575_safeactive_ops,
};

static const struct snd_soc_dapm_widget t575_safeactive_widgets[] = {
    SND_SOC_DAPM_OUTPUT("OUT"),
};

static const struct snd_soc_component_driver t575_safeactive_component = {
    .name = "tas2562-safeactive",
    .dapm_widgets = t575_safeactive_widgets,
    .num_dapm_widgets = ARRAY_SIZE(t575_safeactive_widgets),
};

static int t575_safeactive_probe(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    struct gpio_desc *sdz;

    if (client->addr != 0x4c)
        return -ENODEV;

    sdz = devm_gpiod_get(dev, "shutdown", GPIOD_ASIS);
    if (IS_ERR(sdz))
        return dev_err_probe(dev, PTR_ERR(sdz),
                             "SDZ acquisition failed\n");

    if (gpiod_is_active_low(sdz))
        return -EINVAL;

    int ret = gpiod_direction_output(sdz, 0);
    if (ret)
        return ret;

    i2c_set_clientdata(client, sdz);

    dev_info(dev, "Stage E4D: amplifier held in hardware shutdown\n");

    if (!i2c_check_functionality(client->adapter,
                                 I2C_FUNC_SMBUS_BYTE_DATA))
        return -EOPNOTSUPP;

    ret = devm_snd_soc_register_component(
        dev, &t575_safeactive_component,
        &t575_safeactive_dai, 1);
    if (ret)
        return ret;

    return device_create_file(dev, &dev_attr_safeactive);
}

static void t575_safeactive_shutdown(struct i2c_client *client)
{
    struct gpio_desc *sdz = i2c_get_clientdata(client);

    device_remove_file(&client->dev, &dev_attr_safeactive);

    mutex_lock(&safeactive_lock);
    gpiod_set_value_cansleep(sdz, 0);
    mutex_unlock(&safeactive_lock);
}

static int t575_safeactive_suspend(struct device *dev)
{
    struct gpio_desc *sdz = dev_get_drvdata(dev);

    mutex_lock(&safeactive_lock);
    safeactive_suspended = true;
    gpiod_set_value_cansleep(sdz, 0);
    mutex_unlock(&safeactive_lock);

    return 0;
}

static int t575_safeactive_resume(struct device *dev)
{
    struct gpio_desc *sdz = dev_get_drvdata(dev);

    mutex_lock(&safeactive_lock);
    gpiod_set_value_cansleep(sdz, 0);
    safeactive_suspended = false;
    mutex_unlock(&safeactive_lock);

    return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(t575_safeactive_pm,
    t575_safeactive_suspend, t575_safeactive_resume);

static const struct of_device_id t575_safeactive_of[] = {
    { .compatible = "samsung,t575-tas2562-safeactive" },
    { }
};

MODULE_DEVICE_TABLE(of, t575_safeactive_of);

static struct i2c_driver t575_safeactive_driver = {
    .driver = {
        .name = "t575-tas2562-safeactive",
        .of_match_table = t575_safeactive_of,
        .pm = pm_sleep_ptr(&t575_safeactive_pm),
    },
    .probe = t575_safeactive_probe,
    .remove = t575_safeactive_shutdown,
    .shutdown = t575_safeactive_shutdown,
};

module_i2c_driver(t575_safeactive_driver);

MODULE_DESCRIPTION("SM-T575 E4D restricted activation candidate");
MODULE_LICENSE("GPL");
