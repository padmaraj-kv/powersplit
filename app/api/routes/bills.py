"""
Bill management API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.core.database import get_database
from app.database.repositories import SQLBillRepository, SQLUserRepository, SQLPaymentRepository
from app.services.bill_query_service import BillQueryService
from app.services.payment_confirmation_service import PaymentConfirmationService
from app.models.schemas import BillSummary, BillDetails, PaymentStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/bills", tags=["bills"])


def get_bill_query_service():
    """Dependency to get bill query service"""
    db = get_database()
    bill_repo = SQLBillRepository(db)
    user_repo = SQLUserRepository(db)
    payment_repo = SQLPaymentRepository(db)
    return BillQueryService(bill_repo, user_repo, payment_repo)


def get_payment_confirmation_service():
    """Dependency to get payment confirmation service"""
    db = get_database()
    payment_repo = SQLPaymentRepository(db)
    bill_repo = SQLBillRepository(db)
    return PaymentConfirmationService(payment_repo, bill_repo)


@router.get("/user/{phone_number}")
async def get_user_bills(
    phone_number: str,
    limit: int = Query(default=20, le=100),
    status: Optional[str] = Query(default=None),
    bill_service: BillQueryService = Depends(get_bill_query_service)
):
    """
    Get bills for a user by phone number
    Implements requirement 6.1 for bill history retrieval
    """
    try:
        bills = await bill_service.get_user_bills_by_phone(
            phone_number=phone_number,
            limit=limit,
            status_filter=status
        )
        
        return {
            "status": "success",
            "bills": bills,
            "count": len(bills),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving user bills: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve bills")


@router.get("/{bill_id}")
async def get_bill_details(
    bill_id: str,
    user_phone: str = Query(..., description="User phone number for authorization"),
    bill_service: BillQueryService = Depends(get_bill_query_service)
):
    """
    Get detailed bill information
    Implements requirement 6.3 for complete bill information
    """
    try:
        bill_details = await bill_service.get_bill_details(
            bill_id=bill_id,
            user_phone=user_phone
        )
        
        if not bill_details:
            raise HTTPException(status_code=404, detail="Bill not found or access denied")
        
        return {
            "status": "success",
            "bill": bill_details,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving bill details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve bill details")


@router.get("/{bill_id}/status")
async def get_bill_status(
    bill_id: str,
    user_phone: str = Query(..., description="User phone number for authorization"),
    bill_service: BillQueryService = Depends(get_bill_query_service)
):
    """
    Get bill payment status
    Implements requirement 6.2 for payment status display
    """
    try:
        bill_status = await bill_service.get_bill_payment_status(
            bill_id=bill_id,
            user_phone=user_phone
        )
        
        if not bill_status:
            raise HTTPException(status_code=404, detail="Bill not found or access denied")
        
        return {
            "status": "success",
            "bill_status": bill_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving bill status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve bill status")


@router.post("/{bill_id}/reminders")
async def send_payment_reminders(
    bill_id: str,
    user_phone: str = Query(..., description="User phone number for authorization"),
    participant_phones: Optional[List[str]] = None,
    bill_service: BillQueryService = Depends(get_bill_query_service)
):
    """
    Send payment reminders to unpaid participants
    Implements requirement 6.4 for resending payment requests
    """
    try:
        result = await bill_service.send_payment_reminders(
            bill_id=bill_id,
            user_phone=user_phone,
            participant_phones=participant_phones
        )
        
        return {
            "status": "success",
            "reminders_sent": result.get("reminders_sent", 0),
            "failed_reminders": result.get("failed_reminders", 0),
            "details": result.get("details", []),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending payment reminders: {e}")
        raise HTTPException(status_code=500, detail="Failed to send payment reminders")


@router.post("/{bill_id}/participants/{participant_phone}/confirm-payment")
async def confirm_payment(
    bill_id: str,
    participant_phone: str,
    confirmation_service: PaymentConfirmationService = Depends(get_payment_confirmation_service)
):
    """
    Confirm payment for a participant
    Implements requirement 5.2 for payment status updates
    """
    try:
        result = await confirmation_service.process_payment_confirmation(
            participant_phone=participant_phone,
            bill_id=bill_id,
            confirmation_message="Payment confirmed via API"
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400, 
                detail=result.get("message", "Failed to confirm payment")
            )
        
        return {
            "status": "success",
            "message": result.get("message"),
            "bill_completed": result.get("bill_completed", False),
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        raise HTTPException(status_code=500, detail="Failed to confirm payment")


@router.get("/statistics/overview")
async def get_bill_statistics(
    days_back: int = Query(default=30, le=365),
    bill_service: BillQueryService = Depends(get_bill_query_service)
):
    """
    Get bill statistics overview
    """
    try:
        since_date = datetime.now() - timedelta(days=days_back)
        stats = await bill_service.get_bill_statistics(since_date=since_date)
        
        return {
            "status": "success",
            "statistics": stats,
            "period_days": days_back,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving bill statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/health")
async def bills_health_check():
    """Health check for bills API"""
    try:
        # Test database connectivity
        db = get_database()
        await db.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "service": "bills-api",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Bills API health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "bills-api",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )