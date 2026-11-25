// SPDX-License-Identifier: GPL-2.0-only
#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/pm.h>
#include <sound/soc.h>

static bool allow_activation;

static const struct kernel_param_ops locked_param_ops = {
    .get = param_get_bool,
};

module_param_cb(allow_activation, &locked_param_ops,
                &allow_activation, 0400);

static int locked_startup(struct snd_pcm_substream *substream,
                          struct snd_soc_dai *dai)
{
    struct gpio_desc *sdz = dev_get_drvdata(dai->dev);

    if (!sdz)
        return -ENODEV;

    gpiod_set_value_cansleep(sdz, 0);
    return -EPERM;
}

static const struct snd_soc_dai_ops locked_ops = {
    .startup = locked_startup,
};

static struct snd_soc_dai_driver locked_dai = {
    .name = "tas2562-safeactive",
    .playback = {
        .stream_name = "Playback",
        .channels_min = 2,
        .channels_max = 2,
        .rates = SNDRV_PCM_RATE_48000,
        .formats = SNDRV_PCM_FMTBIT_S32_LE,
    },
    .ops = &locked_ops,
};

static const struct snd_soc_dapm_widget locked_widgets[] = {
    SND_SOC_DAPM_OUTPUT("OUT"),
};

static const struct snd_soc_component_driver locked_component = {
    .name = "tas2562-safeactive",
    .dapm_widgets = locked_widgets,
    .num_dapm_widgets = ARRAY_SIZE(locked_widgets),
};

static int locked_probe(struct i2c_client *client)
{
    struct device *dev = &client->dev;
    struct gpio_desc *sdz;
    int ret;

    if (client->addr != 0x4c)
        return -ENODEV;

    sdz = devm_gpiod_get(dev, "shutdown", GPIOD_ASIS);
    if (IS_ERR(sdz))
        return PTR_ERR(sdz);

    if (gpiod_is_active_low(sdz))
        return -EINVAL;

    ret = gpiod_direction_output(sdz, 0);
    if (ret)
        return ret;

    i2c_set_clientdata(client, sdz);

    dev_info(dev, "T575: amplifier held in hardware shutdown\n");

    return devm_snd_soc_register_component(
        dev, &locked_component, &locked_dai, 1);
}

static void locked_shutdown(struct i2c_client *client)
{
    struct gpio_desc *sdz = i2c_get_clientdata(client);

    if (sdz)
        gpiod_set_value_cansleep(sdz, 0);
}

static int locked_pm(struct device *dev)
{
    struct gpio_desc *sdz = dev_get_drvdata(dev);

    if (sdz)
        gpiod_set_value_cansleep(sdz, 0);

    return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(locked_pm_ops,
                                locked_pm, locked_pm);

static const struct of_device_id locked_of_match[] = {
    { .compatible = "samsung,t575-tas2562-safeactive" },
    { }
};

MODULE_DEVICE_TABLE(of, locked_of_match);

static struct i2c_driver locked_driver = {
    .driver = {
        .name = "t575-tas2562-safeactive",
        .of_match_table = locked_of_match,
        .pm = pm_sleep_ptr(&locked_pm_ops),
    },
    .probe = locked_probe,
    .remove = locked_shutdown,
    .shutdown = locked_shutdown,
};

module_i2c_driver(locked_driver);

MODULE_DESCRIPTION("SM-T575 permanently locked speaker component");
MODULE_LICENSE("GPL");
