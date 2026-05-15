from __future__ import annotations

import wave
from pathlib import Path

import torch

import demucs.audio
import demucs.separate


def save_wav_with_stdlib(
    wav: torch.Tensor,
    path: str | Path,
    samplerate: int,
    bitrate: int = 320,
    clip: str = "rescale",
    bits_per_sample: int = 16,
    as_float: bool = False,
    preset: int = 2,
) -> None:
    path = Path(path)
    if path.suffix.lower() != ".wav":
        return demucs.audio.save_audio(
            wav,
            path,
            samplerate=samplerate,
            bitrate=bitrate,
            clip=clip,
            bits_per_sample=bits_per_sample,
            as_float=as_float,
            preset=preset,
        )

    clipped = demucs.audio.prevent_clip(wav, mode=clip).detach().cpu().float()
    if clipped.ndim == 1:
        clipped = clipped.unsqueeze(0)
    clipped = clipped.clamp(-1, 1)
    pcm = (clipped.transpose(0, 1).contiguous().numpy() * 32767.0).astype("<i2")

    with wave.open(str(path), "wb") as output:
        output.setnchannels(clipped.shape[0])
        output.setsampwidth(2)
        output.setframerate(samplerate)
        output.writeframes(pcm.tobytes())


demucs.separate.save_audio = save_wav_with_stdlib
main = demucs.separate.main


if __name__ == "__main__":
    main()
