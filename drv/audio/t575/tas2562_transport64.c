// SPDX-License-Identifier: GPL-2.0
/*
 * SM-T575 Stage E4A 64-clock silent transport.
 * Registers an ASoC DAI with the amplifier held in shutdown.
 */

#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/gpio/consumer.h>
#include <linux/of.h>
#include <sound/soc.h>
#include <sound/pcm.h>

static int t575_transport64_startup(
    struct snd_pcm_substream *substream,
    struct snd_soc_dai *dai)
{
    struct gpio_desc *sdz = dev_get_drvdata(dai->dev);

    if (!sdz)
        return -ENODEV;

    gpiod_set_value_cansleep(sdz, 0);

    dev_info(dai->dev,
             "E4A: silent PCM transport; amplifier remains disabled\n");
    return 0;
}

static const struct snd_soc_dai_ops t575_transport64_ops = {
    .startup = t575_transport64_startup,
};

static struct snd_soc_dai_driver t575_transport64_dai = {
    .name = "tas2562-transport64",
    .playback = {
        .stream_name = "Playback",
        .channels_min = 2,
        .channels_max = 2,
        .rates = SNDRV_PCM_RATE_48000,
        .formats = SNDRV_PCM_FMTBIT_S32_LE,
    },
    .ops = &t575_transport64_ops,
};

static const struct snd_soc_dapm_widget t575_transport64_widgets[] = {
    SND_SOC_DAPM_OUTPUT("OUT"),
};

static const struct snd_soc_component_driver t575_transport64_component = {
    .name = "tas2562-transport64",
    .dapm_widgets = t575_transport64_widgets,
    .num_dapm_widgets = ARRAY_SIZE(t575_transport64_widgets),
};

static int t575_transport64_probe(struct i2c_client *client)
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

    dev_info(dev, "Stage E4A: amplifier held in hardware shutdown\n");

    return devm_snd_soc_register_component(
        dev, &t575_transport64_component,
        &t575_transport64_dai, 1);
}

static void t575_transport64_shutdown(struct i2c_client *client)
{
    struct gpio_desc *sdz = i2c_get_clientdata(client);

    gpiod_set_value_cansleep(sdz, 0);
}

static const struct of_device_id t575_transport64_of[] = {
    { .compatible = "samsung,t575-tas2562-transport64" },
    { }
};

MODULE_DEVICE_TABLE(of, t575_transport64_of);

static struct i2c_driver t575_transport64_driver = {
    .driver = {
        .name = "t575-tas2562-transport64",
        .of_match_table = t575_transport64_of,
    },
    .probe = t575_transport64_probe,
    .remove = t575_transport64_shutdown,
    .shutdown = t575_transport64_shutdown,
};

module_i2c_driver(t575_transport64_driver);

MODULE_DESCRIPTION("SM-T575 Stage E4A hardware-disabled PCM transport");
MODULE_LICENSE("GPL");
