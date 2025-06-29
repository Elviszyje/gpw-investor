#!/usr/bin/env python
# -*- coding: utf-8 -*-

import uuid
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ImportJobManager:
    """Manager for background import jobs with progress tracking"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.max_job_timeout = 120  # 2 minutes timeout per job (reduced from 5 minutes)
        self.max_file_timeout = 60  # 1 minute timeout per file
    
    def create_job(self, job_type: str = "file_import") -> str:
        """Create a new import job and return its ID"""
        job_id = str(uuid.uuid4())
        
        with self.lock:
            self.jobs[job_id] = {
                'id': job_id,
                'type': job_type,
                'status': 'created',
                'progress': 0,
                'message': 'Job created',
                'created_at': datetime.now(),
                'started_at': None,
                'finished_at': None,
                'total_files': 0,
                'processed_files': 0,
                'current_file': None,
                'stats': {
                    'imported': 0,
                    'skipped': 0,
                    'errors': 0,
                    'files': 0,
                    'processed_files': []
                },
                'error': None
            }
        
        logger.info(f"Created import job {job_id}")
        return job_id
    
    def start_job(self, job_id: str):
        """Mark job as started"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'running'
                self.jobs[job_id]['started_at'] = datetime.now()
                self.jobs[job_id]['message'] = 'Import started'
                logger.info(f"Started import job {job_id}")
    
    def update_progress(self, job_id: str, progress: int, message: Optional[str] = None, 
                       current_file: Optional[str] = None, file_stats: Optional[Dict] = None):
        """Update job progress"""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                job['progress'] = min(100, max(0, progress))
                if message:
                    job['message'] = message
                if current_file:
                    job['current_file'] = current_file
                if file_stats:
                    # Update cumulative stats
                    job['stats']['imported'] += file_stats.get('imported', 0)
                    job['stats']['skipped'] += file_stats.get('skipped', 0)
                    job['stats']['errors'] += file_stats.get('errors', 0)
                    job['stats']['files'] += 1
                    job['processed_files'] += 1
                    
                    # Add file details
                    file_info = {
                        'filename': current_file,
                        'imported': file_stats.get('imported', 0),
                        'skipped': file_stats.get('skipped', 0),
                        'errors': file_stats.get('errors', 0)
                    }
                    if 'error_message' in file_stats:
                        file_info['error_message'] = file_stats['error_message']
                    
                    job['stats']['processed_files'].append(file_info)
                
                logger.debug(f"Updated job {job_id}: {progress}% - {message}")
    
    def set_total_files(self, job_id: str, total_files: int):
        """Set total number of files to process"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['total_files'] = total_files
    
    def complete_job(self, job_id: str, success: bool = True, error: Optional[str] = None):
        """Mark job as completed"""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                job['status'] = 'completed' if success else 'failed'
                job['finished_at'] = datetime.now()
                job['progress'] = 100 if success else job['progress']
                
                if success:
                    job['message'] = f"Import completed successfully. Imported {job['stats']['imported']} records."
                else:
                    job['message'] = f"Import failed: {error}"
                    job['error'] = error
                
                logger.info(f"Completed import job {job_id}: {job['status']}")
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job"""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                if job['status'] == 'running':
                    job['status'] = 'cancelled'
                    job['finished_at'] = datetime.now()
                    job['message'] = 'Job cancelled by user'
                    logger.info(f"Cancelled import job {job_id}")
                    return True
                else:
                    logger.warning(f"Cannot cancel job {job_id}: status is {job['status']}")
                    return False
            else:
                logger.warning(f"Cannot cancel job {job_id}: job not found")
                return False
    
    def check_timeouts(self):
        """Check for timed out jobs and mark them as failed"""
        current_time = datetime.now()
        timed_out_jobs = []
        
        with self.lock:
            for job_id, job in self.jobs.items():
                if job['status'] == 'running':
                    # Check overall job timeout
                    if job['started_at']:
                        job_duration = (current_time - job['started_at']).total_seconds()
                        if job_duration > self.max_job_timeout:
                            timed_out_jobs.append((job_id, f"Job timeout after {job_duration:.0f}s"))
                            continue
                    
                    # Check file-specific timeout (if job has been processing same file too long)
                    # This is more complex to implement accurately, so we'll focus on overall timeout for now
        
        # Mark timed out jobs as failed
        for job_id, reason in timed_out_jobs:
            logger.error(f"Job {job_id} timed out: {reason}")
            self.complete_job(job_id, success=False, error=reason)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current job status"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all jobs (for debugging)"""
        with self.lock:
            return self.jobs.copy()
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.lock:
            jobs_to_remove = []
            for job_id, job in self.jobs.items():
                if job['created_at'] < cutoff_time:
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self.jobs[job_id]
                logger.info(f"Cleaned up old job {job_id}")


# Global job manager instance
job_manager = ImportJobManager()


def run_import_in_background(job_id: str, files_data: list, importer):
    """
    Run import process in background thread with progress tracking
    
    Args:
        job_id: Job identifier
        files_data: List of dictionaries with 'filename' and 'content' keys
        importer: HistoricalDataImporter instance
    """
    import tempfile
    import os
    
    try:
        logger.info(f"Starting background import job {job_id} with {len(files_data)} files")
        job_manager.start_job(job_id)
        job_manager.set_total_files(job_id, len(files_data))
        
        # Process each file
        for i, file_data in enumerate(files_data):
            filename = file_data['filename']
            content = file_data['content']
            
            # Check if job was cancelled
            job_status = job_manager.get_job_status(job_id)
            if job_status and job_status.get('status') == 'cancelled':
                logger.info(f"Job {job_id} was cancelled, stopping processing")
                return
            
            logger.info(f"Processing file {i+1}/{len(files_data)}: {filename} (size: {len(content)} chars)")
            
            try:
                # Update progress
                progress = int((i / len(files_data)) * 80)  # Reserve 20% for final steps
                job_manager.update_progress(
                    job_id, 
                    progress, 
                    f"Processing file {i+1}/{len(files_data)}: {filename}",
                    current_file=filename
                )
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                
                logger.info(f"Created temp file for {filename}: {temp_path}")
                
                # Import file
                file_result = importer.import_single_file(temp_path)
                
                logger.info(f"Import result for {filename}: {file_result.get('status', 'unknown')}")
                
                # Clean up temporary file
                os.unlink(temp_path)
                
                # Extract stats from the import result
                if file_result.get('status') == 'error':
                    file_stats = {
                        'imported': 0,
                        'skipped': 0,
                        'errors': 1,
                        'error_message': file_result.get('error', 'Unknown error')
                    }
                    logger.warning(f"File {filename} failed: {file_result.get('error', 'Unknown error')}")
                else:
                    # Extract stats from nested structure
                    nested_stats = file_result.get('stats', {})
                    file_stats = {
                        'imported': nested_stats.get('imported', 0),
                        'skipped': nested_stats.get('skipped', 0),
                        'errors': nested_stats.get('errors', 0)
                    }
                    logger.info(f"File {filename} processed: {file_stats['imported']} imported, {file_stats['skipped']} skipped, {file_stats['errors']} errors")
                
                # Update progress with file results
                progress = int(((i + 1) / len(files_data)) * 80)
                job_manager.update_progress(
                    job_id,
                    progress,
                    f"Completed {filename}: {file_stats['imported']} imported, {file_stats['skipped']} skipped",
                    current_file=filename,
                    file_stats=file_stats
                )
                
            except Exception as e:
                logger.error(f"Error processing file {filename}: {e}")
                # Record file error
                error_stats = {
                    'imported': 0,
                    'skipped': 0,
                    'errors': 1,
                    'error_message': str(e)
                }
                job_manager.update_progress(
                    job_id,
                    int(((i + 1) / len(files_data)) * 80),
                    f"Error processing {filename}: {str(e)}",
                    current_file=filename,
                    file_stats=error_stats
                )
        
        # Final steps
        logger.info(f"Finalizing import job {job_id}")
        job_manager.update_progress(job_id, 90, "Finalizing import...")
        
        # Skip statistics retrieval to avoid hanging
        # The statistics can be retrieved separately via /api/import/status endpoint
        logger.info(f"Skipping statistics retrieval for job {job_id} to avoid timeout")
        
        # Complete job
        logger.info(f"Completing import job {job_id}")
        job_manager.complete_job(job_id, success=True)
        
    except Exception as e:
        logger.error(f"Import job {job_id} failed with exception: {e}")
        job_manager.complete_job(job_id, success=False, error=str(e))
