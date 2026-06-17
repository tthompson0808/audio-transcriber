"""Acoustic echo cancellation for laptop-speaker capture.

When the owner uses the laptop speakers (no headset), the microphone physically
re-hears the far-end participants. We already capture the speaker output cleanly
as the loopback channel, so we can use it as a reference and subtract the echo
from the mic *before* transcription — leaving the mic channel as the owner only.

Method: a constrained frequency-domain block adaptive filter (overlap-save
block-NLMS / "FDAF"). Steps:
  1. estimate the bulk delay between the loopback and its echo in the mic
     (cross-correlation), and align the reference to it;
  2. adaptively model the residual speaker->mic impulse response and subtract it,
     freezing adaptation during double-talk (Geigel detector) so the owner's own
     voice is never cancelled.

Pure numpy — no native deps to install on a locked-down machine. Runs offline on
the recorded stereo, so it is cheap and re-runnable on existing recordings.
"""
try:
    import numpy as np
except ImportError:
    np = None


def _estimate_delay(mic, ref, max_lag: int, sample_rate: int) -> int:
    """Bulk delay D (samples) so that the echo in mic aligns with ref[n - D]."""
    n = int(min(len(mic), len(ref), sample_rate * 30))  # a 30 s window is plenty
    if n < 256:
        return 0
    m = mic[:n] - mic[:n].mean()
    r = ref[:n] - ref[:n].mean()
    size = 1
    while size < n + max_lag + 1:
        size <<= 1
    M = np.fft.rfft(m, size)
    R = np.fft.rfft(r, size)
    corr = np.fft.irfft(M * np.conj(R), size)  # corr[d] = sum mic[n]*ref[n-d]
    search = np.abs(corr[: max_lag + 1])
    return int(np.argmax(search)) if search.size else 0


def _align_ref(ref, delay: int):
    if delay <= 0:
        return ref
    out = np.zeros_like(ref)
    if delay < len(ref):
        out[delay:] = ref[: len(ref) - delay]
    return out


def _fdaf(mic, ref, taps: int, mu: float, geigel_thresh: float):
    """Constrained overlap-save block-NLMS. Returns the echo-cancelled mic."""
    M = int(taps)
    N = 2 * M
    L = min(len(mic), len(ref))
    mic = mic[:L].astype(np.float64)
    ref = ref[:L].astype(np.float64)

    nblocks = (L + M - 1) // M
    pad = nblocks * M - L
    if pad:
        mic = np.concatenate([mic, np.zeros(pad)])
        ref = np.concatenate([ref, np.zeros(pad)])

    W = np.zeros(N, dtype=np.complex128)   # frequency-domain filter (M taps, zero-padded)
    Pbin = np.zeros(N)                      # running per-bin reference power
    x_buf = np.zeros(N)                     # most recent N reference samples
    out = np.zeros(nblocks * M)
    eps, lam = 1e-8, 0.9
    seeded = False

    for k in range(nblocks):
        x_buf = np.concatenate([x_buf[M:], ref[k * M:(k + 1) * M]])
        X = np.fft.fft(x_buf)
        y = np.fft.ifft(W * X).real[M:]     # echo estimate for this block
        d = mic[k * M:(k + 1) * M]
        e = d - y
        out[k * M:(k + 1) * M] = e

        # Double-talk freeze: if the mic peak clearly exceeds the recent reference
        # peak, the owner is talking over the echo — don't adapt (would cancel them).
        if np.max(np.abs(d)) > geigel_thresh * (np.max(np.abs(x_buf)) + eps):
            continue

        inst = np.abs(X) ** 2
        # Seed the power estimate on the first adapting block, so the cold start
        # doesn't make the normalized step ~1/(1-lam)x too large (an opening burst).
        Pbin = inst if not seeded else lam * Pbin + (1 - lam) * inst
        seeded = True

        E = np.fft.fft(np.concatenate([np.zeros(M), e]))
        grad = np.conj(X) * E / (Pbin + eps)
        g = np.fft.ifft(grad).real
        g[M:] = 0.0                          # constrain to a causal M-tap filter
        W = W + mu * np.fft.fft(g)

    return out[:L]


def cancel_echo(mic, ref, sample_rate: int, cfg: dict):
    """Remove the loopback (ref) echo from the mic. Returns a float32 array.

    Degrades safely: returns the mic unchanged if AEC is off, numpy is missing,
    the clip is too short, or the reference is silent (nothing to cancel).
    """
    if np is None:
        return mic
    aec = cfg.get("capture", {}).get("aec", {})
    if not aec.get("enabled", True):
        return mic

    L = min(len(mic), len(ref))
    if L < sample_rate:  # under ~1 s, not worth it
        return mic
    mic = np.asarray(mic, dtype=np.float64)[:L]
    ref = np.asarray(ref, dtype=np.float64)[:L]
    if np.sqrt(np.mean(ref ** 2)) < 1e-4:  # silent reference
        return mic.astype(np.float32)

    max_lag = int(aec.get("max_delay_ms", 500) * sample_rate / 1000)
    delay = _estimate_delay(mic, ref, max_lag, sample_rate)
    clean = _fdaf(
        mic,
        _align_ref(ref, delay),
        taps=aec.get("filter_taps", 2048),
        mu=aec.get("step_size", 0.4),
        geigel_thresh=aec.get("geigel_threshold", 2.0),
    )

    reduction = 10 * np.log10((np.sum(mic ** 2) + 1e-12) / (np.sum(clean ** 2) + 1e-12))
    print(f"AEC: ref delay {delay} samp ({1000 * delay / sample_rate:.0f} ms), "
          f"mic energy down {reduction:.1f} dB (echo removed)")
    return np.clip(clean, -1.0, 1.0).astype(np.float32)
