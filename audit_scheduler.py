import asyncio
import logging
import os
import sys
from datetime import datetime
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_audit_script():
    """Run the audit.py script with all necessary environment variables."""
    try:
        # Set up environment variables for the subprocess
        env = os.environ.copy()
        
        # Verify required environment variables
        required_vars = [
            'GOOGLE_SHEETS_CREDENTIALS_FILE',
            'GOOGLE_SHEETS_SPREADSHEET_ID',
            'BIRDEYE_API_KEY',
            'CLAUDE_API_KEY',
            'DEFAULT_TOKEN_ADDRESS'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        logger.info("Running audit script...")
        
        # Run audit.py as a subprocess
        process = await asyncio.create_subprocess_exec(
            sys.executable,  # Use the current Python interpreter
            'audit.py',
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for the process to complete and get output
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info("Audit completed successfully")
            if stdout:
                logger.info(f"Output: {stdout.decode()}")
        else:
            logger.error(f"Audit failed with return code {process.returncode}")
            if stderr:
                logger.error(f"Error: {stderr.decode()}")

    except Exception as e:
        logger.error(f"Error running audit script: {e}")

async def scheduler():
    """Run the audit script once, then every 15 minutes."""
    try:
        # Run once immediately
        logger.info("Running initial audit...")
        await run_audit_script()
        logger.info("Initial audit completed. Starting 15-minute schedule...")

        # Then start the 15-minute schedule
        while True:
            # Wait for 15 minutes before next run
            await asyncio.sleep(15 * 60)  # 15 minutes in seconds
            
            # Run the audit
            await run_audit_script()
            
    except Exception as e:
        logger.error(f"Error in scheduler: {e}")

if __name__ == "__main__":
    try:
        # Run the scheduler
        logger.info("Starting scheduler...")
        asyncio.run(scheduler())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler crashed: {e}")
