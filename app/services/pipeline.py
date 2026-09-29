"""Main orchestrator for the Meeting Audio Analysis pipeline."""
import logging
from pathlib import Path

from app.models.schemas import MeetingAnalysisResult, FinalTurn
from app.services.audio_preprocessing import preprocess_audio
from app.services.transcription import transcribe_audio
from app.services.diarization import diarize_audio
from app.services.alignment import align_segments
from app.services.segment_merger import merge_consecutive_turns
from app.services.gender import predict_speakers_gender
from app.services.sentiment import predict_sentiment

logger = logging.getLogger(__name__)

def analyze_meeting(audio_path: str | Path) -> MeetingAnalysisResult:
    """Executes the full Meeting Audio Analysis pipeline."""
    audio_path = Path(audio_path)
    logger.info(f"Starting analysis for {audio_path.name}")
    
    # 1. Preprocessing
    logger.info("Stage 1: Preprocessing")
    prep_result = preprocess_audio(audio_path)
    normalized_path = prep_result.normalized_path
    
    # 2. Transcription
    logger.info("Stage 2: Transcription")
    transcripts = transcribe_audio(normalized_path)
    
    # 3. Diarization
    logger.info("Stage 2: Diarization")
    speakers = diarize_audio(normalized_path)
    
    # 4. Alignment
    logger.info("Stage 2: Alignment")
    aligned_turns = align_segments(transcripts, speakers)
    
    # 5. Merge
    logger.info("Stage 2: Merging")
    merged_turns = merge_consecutive_turns(aligned_turns)
    
    # 6. Gender prediction per speaker
    logger.info("Stage 3: Gender Classification")
    gender_map = predict_speakers_gender(normalized_path, speakers)
    
    # 7. Sentiment prediction per turn & assemble final
    logger.info("Stage 3: Sentiment Classification & Assembly")
    
    final_segments = []
    unique_speakers = set()
    
    for turn in merged_turns:
        unique_speakers.add(turn.speaker)
        
        # Get cached gender for the speaker
        gender_result = gender_map.get(turn.speaker)
        if gender_result is None:
            gender = "unknown"
            g_conf = 0.0
        else:
            gender = gender_result.gender
            g_conf = gender_result.confidence
            
        # Predict sentiment for this turn
        sentiment_result = predict_sentiment(turn.text)
        
        final_segments.append(FinalTurn(
            speaker=turn.speaker,
            gender=gender,
            gender_confidence=g_conf,
            sentiment=sentiment_result.sentiment,
            sentiment_confidence=sentiment_result.confidence,
            start=turn.start,
            end=turn.end,
            text=turn.text
        ))
        
    logger.info("Analysis complete.")
    
    return MeetingAnalysisResult(
        filename=prep_result.original.filename,
        duration=prep_result.original.duration_seconds,
        speaker_count=len(unique_speakers),
        segments=final_segments
    )

