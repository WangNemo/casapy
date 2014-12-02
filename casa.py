"""Core of CASA-type sound analysis system."""

import numpy as np
import scipy.interpolate
import scipy.signal

import sbpca
import SAcC

# pitchogram
#
# track_pitch
#
# track_multi_pitch
#
# spectrum_for_pitch


"""
Plan:
 - calculate pitch posteriors with SAcC
 - Find one or more pitch tracks with multi-hyp viterbi
 - implement estimation of pitch envelope/mask from subband autoco
 - something to stitch-on unvoiced parts
   - unvoiced parts as segmented residual
   - continuity-based connection
 - pitch track fragments & re-stitching
"""

class casa(object):
  """CASA analysis object."""

  def __init__(self, config):
    self.fbank = sbpca.filterbank(
      config["sample_rate"],
      config["fbank_min_freq"],
      config["fbank_bpo"],
      config["fbank_num_bands"],
      config["fbank_q"],
      config["fbank_order"])
    self.ac_win = config["ac_win_sec"]
    self.ac_hop = config["ac_hop_sec"]
    self.srate = config["sample_rate"]


  def correlogram(self, audio):
    """Calculate subband autocorrelation."""
    subbands, freqs = sbpca.subbands(audio, self.srate, self.fbank)
    correlogram = sbpca.autoco(subbands, self.srate,
                               self.ac_win, self.ac_hop, normalize=False)
    return correlogram

  def env_for_pitch(self, correlogram, pitch_hz):
    """Estimate the envelope for a given pitch."""
    n_subbands, n_lags, n_frames = np.shape(correlogram)
    assert n_frames == len(pitch_hz), "n_frames %d != len(pitch) %d" % (
      n_frames, len(pitch_hz))
    # Map pitch to correlogram bins
    pitch_lag_bins = np.round(self.srate/(pitch_hz + (pitch_hz==0))).astype(int)
    env = np.zeros((n_subbands, n_frames))
    for time_ in range(n_frames):
      if pitch_hz[time_] > 0:
        env[:, time_] = (correlogram[:, pitch_lag_bins[time_], time_] /
                         correlogram[:, 0, time_])
    return env

  def apply_tf_mask(self, audio, mask):
    """Modulate subband-filtered audio according to a mask.

    Args:
      audio: Input waveform.
      mask: Gain mask, <subbands> x <time_frames>.

    Returns:
      audio_out: Reconstructed audio.
    """
    n_subbands, n_frames = np.shape(mask)
    n_audio = np.shape(audio)[0]
    win_samps = int(round(self.srate * self.ac_hop))
    # Work one subband at a time, add them up.
    assert n_subbands == len(self.fbank.b_i), (
      "Mask rows %d != num subband filters %d" % (n_subbands,
                                                  len(self.fbank.b_i)))
    audio_out = np.zeros(len(audio))
    print "n_audio=", n_audio, "n_frame=", n_frames, "win_samps=", win_samps
    for subband in xrange(n_subbands):
      subband_audio = scipy.signal.lfilter(self.fbank.b_i[subband, ],
                                           self.fbank.a_i[subband, ],
                                           audio)
      interpolator = scipy.interpolate.interp1d(np.r_[-1.0,
                                                      np.arange(float(n_frames))],
                                                np.r_[0.0, mask[subband, ]])
      gains = interpolator(np.arange(float(n_audio))/win_samps)
      audio_out += gains * subband_audio
    return audio_out


def test():
  """Testing the casa."""
  pass

test_config = {"sample_rate": 16000,
               "fbank_min_freq": 125,
               "fbank_bpo": 6,
               "fbank_num_bands": 24,
               "fbank_q": 8,
               "fbank_order": 2,
               "ac_win_sec": 0.025,
               "ac_hop_sec": 0.010}
