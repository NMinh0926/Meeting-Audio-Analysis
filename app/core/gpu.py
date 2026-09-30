"""GPU memory housekeeping shared by the model services."""


def release_cached_memory() -> None:
    """Return the blocks PyTorch's caching allocator keeps after a stage to the driver.

    Whisper runs on CTranslate2, which cannot use PyTorch's cache: without this, memory held after
    diarization of one job leaves too little for transcription of the next on a 4 GB card.
    """
    import torch

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
