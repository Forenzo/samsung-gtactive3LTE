// SPDX-License-Identifier: GPL-2.0-only
/*
 * SM-T575 experimental speaker-only ASoC card (compile validation only).
 * Existing SM-T570 RT5665/RT5510 sound card is deliberately untouched.
 *
 * Never enable the matching DTS node before validating TAS2562 power,
 * clocking and audio routing, plus a reliable non-wiping restore path.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <sound/soc.h>

static const struct snd_soc_dapm_widget t575_widgets[] = {
	SND_SOC_DAPM_SPK("Speaker", NULL),
};

static const struct snd_kcontrol_new t575_controls[] = {
	SOC_DAPM_PIN_SWITCH("Speaker"),
};

static int t575_parse_dai(struct device *dev, struct device_node *node,
			  const char *name,
			  struct snd_soc_dai_link_component *component)
{
	struct device_node *child;
	int ret;

	child = of_get_child_by_name(node, name);
	if (!child)
		return dev_err_probe(dev, -EINVAL, "missing %s node\n", name);
	ret = snd_soc_of_get_dlc(child, NULL, component, 0);
	of_node_put(child);
	if (ret)
		return dev_err_probe(dev, ret, "invalid %s sound-dai\n", name);
	return 0;
}

static int t575_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct device_node *speaker, *np = dev->of_node;
	struct snd_soc_dai_link_component *components;
	struct snd_soc_dai_link *link;
	struct snd_soc_card *card;
	int ret;

	card = devm_kzalloc(dev, sizeof(*card), GFP_KERNEL);
	link = devm_kzalloc(dev, sizeof(*link), GFP_KERNEL);
	components = devm_kcalloc(dev, 3, sizeof(*components), GFP_KERNEL);
	if (!card || !link || !components)
		return -ENOMEM;

	speaker = of_get_child_by_name(np, "speaker-dai-link");
	if (!speaker)
		return dev_err_probe(dev, -EINVAL, "missing speaker-dai-link\n");

	link->name = "T575 Speaker";
	link->stream_name = "T575 Speaker";
	link->playback_only = 1;
	link->cpus = &components[0];
	link->num_cpus = 1;
	link->codecs = &components[1];
	link->num_codecs = 1;
	link->platforms = &components[2];
	link->num_platforms = 1;

	ret = t575_parse_dai(dev, speaker, "cpu", link->cpus);
	if (ret)
		goto out;
	link->platforms->of_node = link->cpus->of_node;
	ret = t575_parse_dai(dev, speaker, "codec", link->codecs);
	if (ret)
		goto out;

	/*
	 * Candidate inherited I2S format from Wi-Fi ABOX UAIF1. Its use on
	 * the LTE TAS2562 path has not been validated on physical hardware.
	 */
	link->dai_fmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
			SND_SOC_DAIFMT_CBC_CFC;

	card->dev = dev;
	card->owner = THIS_MODULE;
	card->name = "GalaxyTabActive3LTE-Test";
	card->dai_link = link;
	card->num_links = 1;
	card->dapm_widgets = t575_widgets;
	card->num_dapm_widgets = ARRAY_SIZE(t575_widgets);
	card->controls = t575_controls;
	card->num_controls = ARRAY_SIZE(t575_controls);
	/*
	 * Leave card routing unclaimed until the exact TAS2562 DAPM widgets
	 * and the tablet's real speaker path have been verified.
	 */
	card->fully_routed = false;
	ret = devm_snd_soc_register_card(dev, card);
out:
	of_node_put(speaker);
	return ret;
}

static const struct of_device_id t575_audio_match[] = {
	{ .compatible = "samsung,gtactive3lte-tas2562-audio" },
	{ }
};
MODULE_DEVICE_TABLE(of, t575_audio_match);

static struct platform_driver t575_audio_driver = {
	.driver = {
		.name = "gtactive3lte-tas2562-audio",
		.of_match_table = t575_audio_match,
		.pm = &snd_soc_pm_ops,
	},
	.probe = t575_probe,
};
module_platform_driver(t575_audio_driver);

MODULE_DESCRIPTION("SM-T575 ABOX UAIF1/TAS2562 prototype (disabled)");
MODULE_LICENSE("GPL");
