// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Galaxy Tab Active3 (SM-T570/T575) audio card:
 * Exynos9810 A-Box UAIF0 <-> Realtek RT5665 (headset, mics),
 * A-Box UAIF1 <-> TI TAS2562 (LTE speaker candidate, unverified).
 *
 * Copyright (c) 2026 dixonSolutions
 *
 * Link setup follows Samsung's sound/soc/samsung/gtactive3-rt5665-rt5510.c:
 * all UAIFs are I2S, normal clock polarity, A-Box clock provider, and the
 * RT5665 system clock comes from PLL1 locked to BCLK1 (rate * 512).
 */

#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#include <sound/jack.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>

#include "../codecs/rt5665.h"

enum {
	GTA3_LINK_HEADSET,
	GTA3_LINK_SPEAKER,
	GTA3_NUM_LINKS,
};

/*
 * Samsung's stock Active3 machine driver explicitly ungates UAIF0 BCLK
 * before asking RT5665 to lock PLL1. Track both directions so the clock
 * stays enabled while either headphones or microphone is active.
 *
 * This affects UAIF0 only. TAS2562 / UAIF1 safety is unchanged.
 */
/*
 * Current Exynos9810 ABOX CPU DAI returns -EINVAL to set_tristate().
 * This is not a usable BCLK-gating interface on this kernel.
 * Continue with RT5665 PLL configuration in that case; only undo
 * tristate when a previous enable call actually succeeded.
 */
struct gta3_headset_clock_state {
	struct mutex lock;
	bool active[2];
	bool tristate_unsupported;
	bool clock_ungated;
};

static int gta3_headset_hw_params(struct snd_pcm_substream *substream,
				  struct snd_pcm_hw_params *params)
{
	struct snd_soc_pcm_runtime *rtd = snd_soc_substream_to_rtd(substream);
	struct snd_soc_dai *codec_dai = snd_soc_rtd_to_codec(rtd, 0);
	struct gta3_headset_clock_state *state = snd_soc_card_get_drvdata(rtd->card);
	unsigned int rate = params_rate(params);
	unsigned int bclk = rate * params_width(params) * params_channels(params);
	unsigned int sysclk = rate * 512;
	int ret;

	mutex_lock(&state->lock);
	if (!state->active[SNDRV_PCM_STREAM_PLAYBACK] &&
	    !state->active[SNDRV_PCM_STREAM_CAPTURE] &&
	    !state->tristate_unsupported) {
		ret = snd_soc_dai_set_tristate(snd_soc_rtd_to_cpu(rtd, 0), 0);
		if (ret == -EINVAL || ret == -ENOTSUPP) {
			state->tristate_unsupported = true;
			dev_warn_once(rtd->dev,
				      "ABOX UAIF0 has no tristate operation (%d); continuing with codec PLL setup\n",
				      ret);
		} else if (ret) {
			dev_err(rtd->dev, "UAIF0 tristate enable failed: %d\n", ret);
			goto out;
		} else {
			state->clock_ungated = true;
		}
	}

	ret = snd_soc_dai_set_pll(codec_dai, 0, RT5665_PLL1_S_BCLK1,
				  bclk, sysclk);
	if (ret) {
		dev_err(rtd->dev, "RT5665 PLL1 (BCLK1 %u -> %u): %d\n",
			bclk, sysclk, ret);
		goto rollback;
	}

	ret = snd_soc_dai_set_sysclk(codec_dai, RT5665_SCLK_S_PLL1, sysclk,
				     SND_SOC_CLOCK_IN);
	if (ret) {
		dev_err(rtd->dev, "RT5665 sysclk: %d\n", ret);
		goto rollback;
	}

	state->active[substream->stream] = true;
	goto out;

rollback:
	if (state->clock_ungated &&
	    !state->active[SNDRV_PCM_STREAM_PLAYBACK] &&
	    !state->active[SNDRV_PCM_STREAM_CAPTURE]) {
		snd_soc_dai_set_tristate(snd_soc_rtd_to_cpu(rtd, 0), 1);
		state->clock_ungated = false;
	}
out:
	mutex_unlock(&state->lock);
	return ret;
}

static int gta3_headset_hw_free(struct snd_pcm_substream *substream)
{
	struct snd_soc_pcm_runtime *rtd = snd_soc_substream_to_rtd(substream);
	struct gta3_headset_clock_state *state = snd_soc_card_get_drvdata(rtd->card);
	int ret = 0;

	mutex_lock(&state->lock);
	state->active[substream->stream] = false;
	if (state->clock_ungated &&
	    !state->active[SNDRV_PCM_STREAM_PLAYBACK] &&
	    !state->active[SNDRV_PCM_STREAM_CAPTURE]) {
		ret = snd_soc_dai_set_tristate(snd_soc_rtd_to_cpu(rtd, 0), 1);
		if (!ret)
			state->clock_ungated = false;
	}
	mutex_unlock(&state->lock);

	if (ret)
		dev_warn(rtd->dev, "Active3 UAIF0 BCLK disable failed: %d\n", ret);
	return ret;
}

static const struct snd_soc_ops gta3_headset_ops = {
	.hw_params = gta3_headset_hw_params,
	.hw_free = gta3_headset_hw_free,
};

/*
 * Stage C: reject speaker streams until amplifier
 * protection and safe playback are validated.
 */

static int gta3_transport_hw_params(
    struct snd_pcm_substream *substream,
    struct snd_pcm_hw_params *params)
{
    struct snd_soc_pcm_runtime *rtd =
        snd_soc_substream_to_rtd(substream);

    if (params_rate(params) != 48000 ||
        params_channels(params) != 2 ||
        params_format(params) != SNDRV_PCM_FORMAT_S32_LE)
        return -EINVAL;

    dev_info(rtd->dev,
             "E4A: UAIF1 48000 Hz, stereo, S32_LE transport\n");

    return 0;
}

static const struct snd_soc_ops gta3_speaker_transport_ops = {
	.hw_params = gta3_transport_hw_params,
};

static struct snd_soc_jack gta3_headset_jack;

static int gta3_headset_init(struct snd_soc_pcm_runtime *rtd)
{
	struct snd_soc_component *codec = snd_soc_rtd_to_codec(rtd, 0)->component;
	int ret;

	/*
	 * No jack pins: without a working JD source (the stock JD1+JD2 mode is
	 * not in mainline) the jack would stay "unplugged" and keep the
	 * Headphones and Headset Mic pins off. They are plain pin switches.
	 */
	ret = snd_soc_card_jack_new(rtd->card, "Headset Jack",
				    SND_JACK_HEADSET | SND_JACK_BTN_0 |
				    SND_JACK_BTN_1 | SND_JACK_BTN_2 |
				    SND_JACK_BTN_3, &gta3_headset_jack);
	if (ret)
		return ret;

	/* RT5665 jack detection, only if the DT gave it a JD source */
	return snd_soc_component_set_jack(codec, &gta3_headset_jack, NULL);
}

static const struct snd_soc_dapm_widget gta3_widgets[] = {
	SND_SOC_DAPM_HP("Headphones", NULL),
	SND_SOC_DAPM_SPK("Speaker", NULL),
	SND_SOC_DAPM_MIC("Headset Mic", NULL),
	SND_SOC_DAPM_MIC("Main Mic", NULL),
	SND_SOC_DAPM_MIC("Sub Mic", NULL),
};

static const struct snd_kcontrol_new gta3_controls[] = {
	SOC_DAPM_PIN_SWITCH("Headphones"),
	SOC_DAPM_PIN_SWITCH("Headset Mic"),
	SOC_DAPM_PIN_SWITCH("Main Mic"),
	SOC_DAPM_PIN_SWITCH("Sub Mic"),
};

static int gta3_parse_link(struct device *dev, struct device_node *np,
			   const char *name, struct snd_soc_dai_link *link)
{
	struct device_node *child, *sub;
	struct snd_soc_dai_link_component *comp;
	int ret;

	child = of_get_child_by_name(np, name);
	if (!child)
		return dev_err_probe(dev, -EINVAL, "missing %s node\n", name);

	comp = devm_kcalloc(dev, 3, sizeof(*comp), GFP_KERNEL);
	if (!comp) {
		of_node_put(child);
		return -ENOMEM;
	}
	link->cpus = &comp[0];
	link->num_cpus = 1;
	link->codecs = &comp[1];
	link->num_codecs = 1;
	link->platforms = &comp[2];
	link->num_platforms = 1;

	sub = of_get_child_by_name(child, "cpu");
	ret = sub ? snd_soc_of_get_dlc(sub, NULL, link->cpus, 0) : -EINVAL;
	of_node_put(sub);
	if (ret)
		goto out;
	link->platforms->of_node = link->cpus->of_node;

	sub = of_get_child_by_name(child, "codec");
	ret = sub ? snd_soc_of_get_dlc(sub, NULL, link->codecs, 0) : -EINVAL;
	of_node_put(sub);
out:
	of_node_put(child);
	if (ret)
		return dev_err_probe(dev, ret, "%s: bad cpu/codec\n", name);
	return 0;
}

static int gta3_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct device_node *np = dev->of_node;
	struct snd_soc_dai_link *links;
	struct snd_soc_card *card;
	struct gta3_headset_clock_state *headset_clocks;
	int ret;

	card = devm_kzalloc(dev, sizeof(*card), GFP_KERNEL);
	links = devm_kcalloc(dev, GTA3_NUM_LINKS, sizeof(*links), GFP_KERNEL);
	if (!card || !links)
		return -ENOMEM;

	headset_clocks = devm_kzalloc(dev, sizeof(*headset_clocks), GFP_KERNEL);
	if (!headset_clocks)
		return -ENOMEM;
	mutex_init(&headset_clocks->lock);

	card->dev = dev;
	snd_soc_card_set_drvdata(card, headset_clocks);
	card->owner = THIS_MODULE;
	card->dai_link = links;
	card->num_links = GTA3_NUM_LINKS;
	card->dapm_widgets = gta3_widgets;
	card->num_dapm_widgets = ARRAY_SIZE(gta3_widgets);
	card->controls = gta3_controls;
	card->num_controls = ARRAY_SIZE(gta3_controls);
	card->fully_routed = false;

	ret = snd_soc_of_parse_card_name(card, "model");
	if (ret)
		return ret;
	if (!card->name)
		card->name = "GalaxyTabActive3";

	ret = snd_soc_of_parse_audio_routing(card, "audio-routing");
	if (ret)
		return ret;

	links[GTA3_LINK_HEADSET].name = "Headset";
	links[GTA3_LINK_HEADSET].stream_name = "Headset";
	links[GTA3_LINK_HEADSET].ops = &gta3_headset_ops;
	links[GTA3_LINK_HEADSET].init = gta3_headset_init;
	ret = gta3_parse_link(dev, np, "headset-dai-link",
			      &links[GTA3_LINK_HEADSET]);
	if (ret)
		return ret;

	links[GTA3_LINK_SPEAKER].name = "Speaker";
	links[GTA3_LINK_SPEAKER].stream_name = "Speaker";
	links[GTA3_LINK_SPEAKER].playback_only = 1;
	links[GTA3_LINK_SPEAKER].ops = &gta3_speaker_transport_ops;
	ret = gta3_parse_link(dev, np, "speaker-dai-link",
			      &links[GTA3_LINK_SPEAKER]);
	if (ret)
		return ret;

	for (int i = 0; i < GTA3_NUM_LINKS; i++)
		links[i].dai_fmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
				   SND_SOC_DAIFMT_CBC_CFC;

	return devm_snd_soc_register_card(dev, card);
}

static const struct of_device_id gta3_of_match[] = {
	{ .compatible = "samsung,gtactive3lte-transport64" },
	{ }
};
MODULE_DEVICE_TABLE(of, gta3_of_match);

static struct platform_driver gta3_driver = {
	.driver = {
		.name = "gtactive3lte-transport64",
		.of_match_table = gta3_of_match,
	},
	.probe = gta3_probe,
};
module_platform_driver(gta3_driver);

MODULE_DESCRIPTION("SM-T575 E4A unified 64-clock silent speaker transport");
MODULE_LICENSE("GPL");
