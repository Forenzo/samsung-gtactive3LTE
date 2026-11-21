// SPDX-License-Identifier: GPL-2.0
/*
 * SM-T575 Stage C locked amplifier component.
 * Registers an ASoC DAI with the amplifier held in shutdown.
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/of.h>
#include <sound/soc.h>
#include <sound/pcm.h>

static int t575_locked_startup(
    struct snd_pcm_substream *substream,
    struct snd_soc_dai *dai)
{
    dev_warn(dai->dev, "TAS2562 hardware playback locked\n");
    return -EPERM;
}

static const struct snd_soc_dai_ops t575_locked_ops = {
    .startup = t575_locked_startup,
};

static struct snd_soc_dai_driver t575_locked_dai = {
    .name = "tas2562-locked",
    .playback = {
        .stream_name = "Playback",
        .channels_min = 1,
        .channels_max = 2,
        .rates = SNDRV_PCM_RATE_48000,
        .formats = SNDRV_PCM_FMTBIT_S16_LE |
                   SNDRV_PCM_FMTBIT_S24_LE |
                   SNDRV_PCM_FMTBIT_S32_LE,
    },
    .ops = &t575_locked_ops,
};

static const struct snd_soc_dapm_widget t575_locked_widgets[] = {
    SND_SOC_DAPM_OUTPUT("OUT"),
};

static const struct snd_soc_component_driver t575_locked_component = {
    .name = "tas2562-locked",
    .dapm_widgets = t575_locked_widgets,
    .num_dapm_widgets = ARRAY_SIZE(t575_locked_widgets),
};

static int t575_locked_probe(struct i2c_client *client)
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

    dev_info(dev, "Stage C: amplifier held in hardware shutdown\n");

    return devm_snd_soc_register_component(
        dev, &t575_locked_component,
        &t575_locked_dai, 1);
}

static const struct of_device_id t575_locked_of[] = {
    { .compatible = "samsung,t575-tas2562-locked" },
    { }
};

MODULE_DEVICE_TABLE(of, t575_locked_of);

static struct i2c_driver t575_locked_driver = {
    .driver = {
        .name = "t575-tas2562-locked",
        .of_match_table = t575_locked_of,
    },
    .probe = t575_locked_probe,
};

module_i2c_driver(t575_locked_driver);

MODULE_DESCRIPTION("SM-T575 Stage C locked TAS2562 component");
MODULE_LICENSE("GPL");
