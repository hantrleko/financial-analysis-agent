import os
import sys
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import VERSION
from src.pipeline import PipelineConfig, run_pipeline

logger = logging.getLogger(__name__)

HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info("Starting Financial Analysis System (%s)...", VERSION)

    config = PipelineConfig(
        query="latest financial news market trends",
        num_articles=5,
        language="en",
        deep_analysis=True,
        generate_audio=True,
        generate_pdf=True,
        data_dir="data",
        history_dir=HISTORY_DIR,
    )

    result = run_pipeline(config)

    if result.error:
        logger.error("Pipeline failed: %s", result.error)
        return

    logger.info("--- Analysis Report ---")
    logger.info("\n%s", result.report)
    logger.info("-----------------------")

    if result.audio_path:
        logger.info("Audio generated: %s", result.audio_path)
    if result.pdf_path:
        logger.info("PDF generated: %s", result.pdf_path)

    logger.info("Workflow Complete! Run ID: %s", result.run_id)


if __name__ == "__main__":
    main()
