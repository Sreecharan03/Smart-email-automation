#!/usr/bin/env python3
# ====================================
# UNIFIED AI EMAIL ASSISTANT - DRAFT WORKFLOW
# ====================================
# LangGraph workflow for intelligent email reply generation
# Uses Gemini AI to draft replies with human approval before sending

import psycopg2
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
import uuid

# LangGraph imports
from langgraph.graph import StateGraph, START, END

# Our services
import sys
import os

# Add relevant directories to sys.path for module resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../'))
services_dir = os.path.abspath(os.path.join(current_dir, '../services'))
email_assistant_dir = os.path.abspath(os.path.join(current_dir, '../../email-assistant'))

sys.path.append(project_root)
sys.path.append(services_dir)
sys.path.append(email_assistant_dir)

from config import get_config, get_supabase_connection_params

# Google AI imports
import google.generativeai as genai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DraftType(Enum):
    """Types of email drafts"""
    REPLY = "reply"
    FORWARD = "forward"
    NEW = "new"
    FOLLOW_UP = "follow_up"

class DraftTone(Enum):
    """Email tone options"""
    FORMAL = "formal"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    URGENT = "urgent"

class DraftLength(Enum):
    """Email length options"""
    SHORT = "short"          # 1-2 sentences
    MEDIUM = "medium"        # 1-2 paragraphs
    DETAILED = "detailed"    # Multiple paragraphs

class ApprovalStatus(Enum):
    """Draft approval status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"

@dataclass
class EmailContext:
    """Context information from original email thread"""
    original_subject: str
    original_sender: str
    original_body: str
    thread_history: List[Dict[str, Any]] = field(default_factory=list)
    sender_relationship: str = "unknown"  # colleague, customer, vendor, personal
    urgency_level: str = "normal"         # low, normal, high, urgent
    key_topics: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)

@dataclass
class DraftPreferences:
    """User preferences for draft generation"""
    tone: DraftTone = DraftTone.PROFESSIONAL
    length: DraftLength = DraftLength.MEDIUM
    include_greeting: bool = True
    include_closing: bool = True
    signature: str = ""
    custom_instructions: str = ""

@dataclass
class SafetyCheck:
    """Safety check results"""
    is_safe: bool = True
    flagged_content: List[str] = field(default_factory=list)
    sensitivity_level: str = "normal"  # low, normal, high, confidential
    recommendations: List[str] = field(default_factory=list)

@dataclass
class DraftState:
    """State object for draft workflow"""
    # Input
    original_message_id: int
    user_instructions: str = ""
    draft_type: DraftType = DraftType.REPLY
    preferences: DraftPreferences = field(default_factory=DraftPreferences)
    
    # Context Analysis
    email_context: EmailContext = field(
        default_factory=lambda: EmailContext(
            original_subject="",
            original_sender="",
            original_body=""
        )
    )
    
    # Draft Generation
    generated_draft: str = ""
    draft_subject: str = ""
    draft_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Safety & Approval
    safety_check: SafetyCheck = field(default_factory=SafetyCheck)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    human_feedback: str = ""
    
    # Database
    draft_id: Optional[int] = None
    account_id: int = 1  # Gmail account ID
    
    # Processing
    processing_time: float = 0
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=lambda: time.time())

class EmailDraftWorkflow:
    """
    LangGraph workflow for AI-powered email drafting
    
    Workflow Steps:
    1. Analyze Context - Understand original email and thread
    2. Generate Draft - Use Gemini to create reply
    3. Safety Check - Verify content appropriateness
    4. Human Review - Present for approval (pause workflow)
    5. Send Email - Send via Gmail API after approval
    """
    
    def __init__(self):
        """Initialize draft workflow with AI and email services"""
        self.config = get_config()
        self.db_params = get_supabase_connection_params(self.config)
        
        # Initialize Gemini AI
        try:
            genai.configure(api_key=self.config.gemini_api_key)
            self.model_name = self._resolve_gemini_model_name()
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini AI model initialized for drafting: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise
        
        # Create workflow
        self.workflow = self._create_workflow()
        
        logger.info("Email Draft Workflow initialized")
    
    def _create_workflow(self) -> Any:
        """Create the LangGraph draft workflow"""
        workflow = StateGraph(DraftState)
        
        # Add workflow nodes
        workflow.add_node("analyze_context", self._analyze_email_context)
        workflow.add_node("generate_draft", self._generate_ai_draft)
        workflow.add_node("safety_check", self._perform_safety_check)
        workflow.add_node("save_draft", self._save_draft_to_database)
        workflow.add_node("await_approval", self._await_human_approval)
        workflow.add_node("send_email", self._send_approved_email)
        workflow.add_node("finalize", self._finalize_draft)
        
        # Define workflow edges
        workflow.add_edge(START, "analyze_context")
        workflow.add_edge("analyze_context", "generate_draft")
        workflow.add_edge("generate_draft", "safety_check")
        workflow.add_edge("safety_check", "save_draft")
        workflow.add_edge("save_draft", "await_approval")
        
        # Conditional edges based on approval
        workflow.add_conditional_edges(
            "await_approval",
            self._approval_decision,
            {
                "approved": "send_email",
                "rejected": "finalize",
                "needs_revision": "generate_draft"
            }
        )
        
        workflow.add_edge("send_email", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    def _analyze_email_context(self, state: DraftState) -> DraftState:
        """
        Analyze the original email to understand context and requirements
        """
        logger.info(f"Analyzing context for message ID: {state.original_message_id}")
        
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    # Get original email details
                    cur.execute("""
                        SELECT id, account_id, subject, snippet, sender_email, sender_name, 
                               date_sent, thread_id, labels, body_plain
                        FROM email_messages 
                        WHERE id = %s
                    """, (state.original_message_id,))
                    
                    email_row = cur.fetchone()
                    
                    if not email_row:
                        error_msg = f"Email {state.original_message_id} not found"
                        logger.error(error_msg)
                        state.errors.append(error_msg)
                        return state
                    
                    # Extract email data
                    (msg_id, account_id, subject, snippet, sender_email, sender_name, 
                     date_sent, thread_id, labels, body_plain) = email_row
                    state.account_id = account_id
                    if not sender_email:
                        error_msg = f"Email {state.original_message_id} has no sender_email"
                        logger.error(error_msg)
                        state.errors.append(error_msg)
                        return state
                    
                    # Build email context
                    context = EmailContext(
                        original_subject=subject or "",
                        original_sender=sender_email.strip(),
                        original_body=body_plain or snippet or ""
                    )
                    
                    # Get thread history if available
                    if thread_id:
                        cur.execute("""
                            SELECT subject, sender_email, snippet, date_sent
                            FROM email_messages 
                            WHERE thread_id = %s AND id != %s
                            ORDER BY date_sent DESC
                            LIMIT 5
                        """, (thread_id, msg_id))
                        
                        thread_rows = cur.fetchall()
                        context.thread_history = [
                            {
                                "subject": row[0],
                                "sender": row[1],
                                "snippet": row[2],
                                "date": row[3].isoformat() if row[3] else ""
                            }
                            for row in thread_rows
                        ]
                    
                    # Analyze content for key information
                    context.key_topics = self._extract_key_topics(context.original_body)
                    context.action_items = self._extract_action_items(context.original_body)
                    context.urgency_level = self._detect_urgency(context.original_body, labels)
                    context.sender_relationship = self._infer_sender_relationship(sender_email, labels)
                    
                    state.email_context = context
                    
                    # Set draft subject
                    if subject and not subject.lower().startswith(('re:', 'fwd:')):
                        state.draft_subject = f"Re: {subject}"
                    else:
                        state.draft_subject = subject or "Re: Your email"
                    
                    logger.info(f"Context analysis complete: {len(context.key_topics)} topics, {context.urgency_level} urgency")
                    
        except Exception as e:
            error_msg = f"Context analysis failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _generate_ai_draft(self, state: DraftState) -> DraftState:
        """
        Generate email draft using Gemini AI
        """
        logger.info("Generating AI draft using Gemini")
        if state.errors:
            logger.warning("Skipping draft generation due to previous errors")
            return state
        
        try:
            # Build context prompt
            context_prompt = self._build_context_prompt(state)
            
            # Build generation prompt
            generation_prompt = self._build_generation_prompt(state, context_prompt)
            
            logger.debug(f"Generation prompt length: {len(generation_prompt)} characters")
            
            # Generate draft using Gemini
            response = self.model.generate_content(generation_prompt)
            
            if response and response.text:
                # Clean and format the generated text
                draft_text = self._clean_generated_draft(response.text)
                
                # Apply user preferences
                draft_text = self._apply_draft_preferences(draft_text, state.preferences)
                
                state.generated_draft = draft_text
                state.draft_metadata = {
                    "model": self.model_name,
                    "generation_time": time.time() - state.start_time,
                    "prompt_tokens": len(generation_prompt.split()),
                    "response_tokens": len(draft_text.split())
                }
                
                logger.info(f"Generated draft: {len(draft_text)} characters")
                
            else:
                error_msg = "Gemini failed to generate draft content"
                logger.error(error_msg)
                state.errors.append(error_msg)
                
        except Exception as e:
            error_msg = f"Draft generation failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _perform_safety_check(self, state: DraftState) -> DraftState:
        """
        Perform safety checks on generated draft
        """
        logger.info("Performing safety check on draft")
        if state.errors:
            logger.warning("Skipping safety check due to previous errors")
            state.safety_check = SafetyCheck(
                is_safe=False,
                flagged_content=["Skipped due to previous workflow errors"],
                recommendations=["Resolve workflow errors and regenerate the draft"]
            )
            return state
        
        try:
            safety_check = SafetyCheck()
            
            # Check for potentially problematic content
            flagged_items = []
            
            # Check for sensitive information patterns
            sensitive_patterns = [
                (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', "Credit card number"),
                (r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', "SSN pattern"),
                (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "Email address"),
                (r'\b(?:password|token|api[_\s]key|secret)\s*[:=]\s*\S+', "Credentials")
            ]
            
            for pattern, description in sensitive_patterns:
                if re.search(pattern, state.generated_draft, re.IGNORECASE):
                    flagged_items.append(description)
            
            # Check for inappropriate tone/content
            inappropriate_keywords = [
                "angry", "furious", "stupid", "idiot", "hate", "terrible",
                "awful", "disgusting", "pathetic", "useless"
            ]
            
            for keyword in inappropriate_keywords:
                if keyword.lower() in state.generated_draft.lower():
                    flagged_items.append(f"Potentially inappropriate language: {keyword}")
            
            # Set safety status
            safety_check.flagged_content = flagged_items
            safety_check.is_safe = len(flagged_items) == 0
            
            # Generate recommendations
            if flagged_items:
                safety_check.recommendations = [
                    "Review flagged content before sending",
                    "Consider using more professional language",
                    "Remove any sensitive information"
                ]
            
            # Determine sensitivity level
            if any("credentials" in item.lower() or "ssn" in item.lower() 
                   or "credit card" in item.lower() for item in flagged_items):
                safety_check.sensitivity_level = "confidential"
            elif flagged_items:
                safety_check.sensitivity_level = "high"
            else:
                safety_check.sensitivity_level = "normal"
            
            state.safety_check = safety_check
            
            if safety_check.is_safe:
                logger.info("Safety check passed")
            else:
                logger.warning(f"Safety check flagged {len(flagged_items)} issues")
                
        except Exception as e:
            error_msg = f"Safety check failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
            # Default to safe if safety check fails
            state.safety_check = SafetyCheck(is_safe=True)
        
        return state
    
    def _save_draft_to_database(self, state: DraftState) -> DraftState:
        """
        Save draft to database for human review
        """
        logger.info("Saving draft to database")
        if state.errors:
            logger.warning("Skipping draft save due to previous errors")
            return state
        if not state.generated_draft:
            state.errors.append("Cannot save draft: generated draft is empty")
            return state
        
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    # Insert draft record
                    cur.execute("""
                        INSERT INTO email_drafts (
                            draft_uuid, account_id, original_message_id, 
                            recipient_email, subject, body_text, draft_type,
                            tone, length, ai_model_used, generation_prompt,
                            ai_confidence, approval_status, safety_check_passed,
                            safety_issues, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) RETURNING id;
                    """, (
                        str(uuid.uuid4()),
                        state.account_id,
                        state.original_message_id,
                        self._extract_email_address(state.email_context.original_sender),
                        state.draft_subject,
                        state.generated_draft,
                        state.draft_type.value,
                        state.preferences.tone.value,
                        state.preferences.length.value,
                        state.draft_metadata.get("model", self.model_name),
                        "",  # generation_prompt (could store for debugging)
                        0.8,  # ai_confidence (could calculate from response)
                        state.approval_status.value,
                        state.safety_check.is_safe,
                        json.dumps(state.safety_check.flagged_content),
                        datetime.now(timezone.utc)
                    ))
                    
                    state.draft_id = cur.fetchone()[0]
                    conn.commit()
                    
                    logger.info(f"Draft saved with ID: {state.draft_id}")
                    
        except Exception as e:
            error_msg = f"Failed to save draft: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state
    
    def _await_human_approval(self, state: DraftState) -> DraftState:
        """
        Pause workflow for human review and approval
        In production, this would integrate with frontend interface
        """
        logger.info(f"Awaiting human approval for draft {state.draft_id}")
        if state.errors:
            state.approval_status = ApprovalStatus.REJECTED
            state.human_feedback = "Draft rejected due to workflow errors"
            logger.info("Draft rejected due to existing workflow errors")
            return state
        
        # In a real implementation, this would:
        # 1. Send notification to user
        # 2. Display draft in UI
        # 3. Wait for user action
        # 4. Resume workflow based on user decision
        
        # For testing, we'll simulate approval
        if not state.safety_check.flagged_content:
            state.approval_status = ApprovalStatus.APPROVED
            logger.info("Draft auto-approved for testing (no safety issues)")
        else:
            state.approval_status = ApprovalStatus.NEEDS_REVISION
            state.human_feedback = "Please address safety concerns before sending"
            logger.info("Draft needs revision due to safety concerns")
        
        return state
    
    def _approval_decision(self, state: DraftState) -> str:
        """
        Determine next step based on approval status
        """
        if state.errors:
            return ApprovalStatus.REJECTED.value
        return state.approval_status.value
    
    def _send_approved_email(self, state: DraftState) -> DraftState:
        """
        Send the approved email via Gmail API
        """
        logger.info(f"Sending approved draft {state.draft_id}")
        if state.approval_status != ApprovalStatus.APPROVED:
            logger.info("Skipping send because draft is not approved")
            return state
        if state.errors:
            logger.info("Skipping send due to previous errors")
            return state
        
        try:
            # Import Gmail service from backend service module
            from backend.services.gmail.gmail_service import GmailService, SendEmailRequest
            gmail_service = GmailService(account_id=state.account_id)
            
            # Prepare email data
            recipient_email = self._extract_email_address(state.email_context.original_sender)
            if not recipient_email:
                state.errors.append("Email sending failed: recipient email is empty")
                return state
            if not state.generated_draft:
                state.errors.append("Email sending failed: draft body is empty")
                return state
            if not state.draft_subject:
                state.draft_subject = "Re: Your email"
            email_data = {
                "to": recipient_email,
                "subject": state.draft_subject,
                "body": state.generated_draft
            }
            
            # Send email
            sent_message_id = gmail_service.send_email(
                SendEmailRequest(
                    to=[email_data["to"]],
                    subject=email_data["subject"],
                    body_text=email_data["body"],
                    body_html=None
                )
            )
            
            if sent_message_id:
                # Update draft record as sent
                with psycopg2.connect(**self.db_params) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE email_drafts 
                            SET is_sent = TRUE, sent_at = %s, sent_message_id = %s
                            WHERE id = %s
                        """, (
                            datetime.now(timezone.utc),
                            sent_message_id,
                            state.draft_id
                        ))
                        conn.commit()
                
                logger.info(f"Email sent successfully: {sent_message_id}")
                state.draft_metadata["sent_message_id"] = sent_message_id
                
            else:
                error_msg = (
                    f"Failed to send email via Gmail API for account {state.account_id}. "
                    "Re-authenticate this Gmail account if OAuth tokens are invalid."
                )
                logger.error(error_msg)
                state.errors.append(error_msg)
                
        except Exception as e:
            error_msg = f"Email sending failed: {str(e)}"
            logger.error(error_msg)
            state.errors.append(error_msg)
        
        return state

    def _resolve_gemini_model_name(self) -> str:
        """
        Select a valid Gemini model for draft generation.
        Prefers Gemini 2.5 Pro and falls back only if unavailable.
        """
        env_override = os.getenv("GEMINI_DRAFT_MODEL", "").strip()
        preferred_models = [
            env_override,
            "gemini-2.5-pro",
            "models/gemini-2.5-pro",
            "gemini-1.5-pro",
            "models/gemini-1.5-pro",
        ]
        preferred_models = [m for m in preferred_models if m]

        try:
            available_models = []
            for model in genai.list_models():
                methods = set(getattr(model, "supported_generation_methods", []) or [])
                if "generateContent" in methods:
                    available_models.append(getattr(model, "name", ""))

            for candidate in preferred_models:
                if candidate in available_models:
                    return candidate
                prefixed = candidate if candidate.startswith("models/") else f"models/{candidate}"
                if prefixed in available_models:
                    return prefixed

            if available_models:
                return available_models[0]
        except Exception as e:
            logger.warning(f"Could not list Gemini models, using preferred default: {e}")

        # Fallback when model listing is unavailable
        return preferred_models[0]
    
    def _finalize_draft(self, state: DraftState) -> DraftState:
        """
        Finalize draft workflow and generate statistics
        """
        state.processing_time = time.time() - state.start_time
        
        logger.info("=== DRAFT WORKFLOW COMPLETE ===")
        logger.info(f"Draft ID: {state.draft_id}")
        logger.info(f"Type: {state.draft_type.value}")
        logger.info(f"Status: {state.approval_status.value}")
        logger.info(f"Processing Time: {state.processing_time:.3f}s")
        logger.info(f"Safety Issues: {len(state.safety_check.flagged_content)}")
        
        if state.errors:
            logger.warning(f"Errors: {len(state.errors)}")
            for error in state.errors:
                logger.warning(f"  - {error}")
        
        return state
    
    def _build_context_prompt(self, state: DraftState) -> str:
        """Build context information for AI prompt"""
        context = state.email_context
        
        context_parts = [
            f"Original Email Subject: {context.original_subject}",
            f"From: {context.original_sender}",
            f"Content: {context.original_body[:500]}...",  # Limit length
        ]
        
        if context.key_topics:
            context_parts.append(f"Key Topics: {', '.join(context.key_topics)}")
        
        if context.action_items:
            context_parts.append(f"Action Items: {', '.join(context.action_items)}")
        
        if context.thread_history:
            context_parts.append("Thread History:")
            for msg in context.thread_history[:2]:  # Limit history
                context_parts.append(f"- {msg['sender']}: {msg['snippet'][:100]}...")
        
        return "\n".join(context_parts)
    
    def _build_generation_prompt(self, state: DraftState, context: str) -> str:
        """Build the complete generation prompt for Gemini"""
        
        preferences = state.preferences
        
        prompt_parts = [
            "You are an AI assistant helping to draft a professional email reply.",
            "",
            "CONTEXT:",
            context,
            "",
            "REQUIREMENTS:",
            f"- Tone: {preferences.tone.value}",
            f"- Length: {preferences.length.value}",
            f"- Include greeting: {'Yes' if preferences.include_greeting else 'No'}",
            f"- Include closing: {'Yes' if preferences.include_closing else 'No'}",
            "",
            "USER INSTRUCTIONS:",
            state.user_instructions or "Generate an appropriate reply to this email.",
            "",
            "GUIDELINES:",
            "1. Be professional and courteous",
            "2. Address the main points from the original email",
            "3. Be clear and concise",
            "4. Use appropriate business email format",
            "5. Do not include sensitive information",
            "",
            "Generate the email body text only (no subject line):"
        ]
        
        return "\n".join(prompt_parts)
    
    def _clean_generated_draft(self, draft_text: str) -> str:
        """Clean and format generated draft text"""
        # Remove any markdown formatting
        draft_text = re.sub(r'\*\*(.*?)\*\*', r'\1', draft_text)  # Bold
        draft_text = re.sub(r'\*(.*?)\*', r'\1', draft_text)      # Italic
        
        # Clean up spacing
        draft_text = re.sub(r'\n\s*\n\s*\n', '\n\n', draft_text)  # Multiple newlines
        draft_text = draft_text.strip()
        
        return draft_text
    
    def _apply_draft_preferences(self, draft_text: str, preferences: DraftPreferences) -> str:
        """Apply user preferences to draft formatting"""
        
        # Add signature if provided
        if preferences.signature:
            if not draft_text.endswith('\n'):
                draft_text += '\n'
            draft_text += f"\n{preferences.signature}"
        
        # Length adjustments could be made here
        if preferences.length == DraftLength.SHORT:
            # Could truncate or ask for shorter version
            pass
        
        return draft_text
    
    def _extract_key_topics(self, text: str) -> List[str]:
        """Extract key topics from email text"""
        # Simple keyword extraction - could be enhanced with NLP
        common_topics = [
            "meeting", "project", "deadline", "budget", "proposal",
            "invoice", "payment", "schedule", "report", "update"
        ]
        
        found_topics = []
        text_lower = text.lower()
        
        for topic in common_topics:
            if topic in text_lower:
                found_topics.append(topic)
        
        return found_topics[:5]  # Limit to 5 topics
    
    def _extract_action_items(self, text: str) -> List[str]:
        """Extract action items from email text"""
        # Look for action-oriented phrases
        action_patterns = [
            r'(?:please|could you|can you|need to|should|must)\s+([^.!?]+)',
            r'(?:let me know|send|provide|review|confirm)\s+([^.!?]+)'
        ]
        
        action_items = []
        for pattern in action_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                action = match.group(0).strip()
                if len(action) > 10 and len(action) < 100:  # Reasonable length
                    action_items.append(action)
        
        return action_items[:3]  # Limit to 3 items
    
    def _detect_urgency(self, text: str, labels: List[str]) -> str:
        """Detect urgency level from email content and labels"""
        urgent_keywords = ["urgent", "asap", "immediately", "rush", "critical", "emergency"]
        high_keywords = ["important", "priority", "soon", "deadline"]
        
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in urgent_keywords):
            return "urgent"
        elif any(keyword in text_lower for keyword in high_keywords):
            return "high"
        elif labels and "IMPORTANT" in labels:
            return "high"
        else:
            return "normal"
    
    def _infer_sender_relationship(self, sender_email: str, labels: List[str]) -> str:
        """Infer relationship with sender"""
        domain = sender_email.split('@')[-1].lower() if '@' in sender_email else ""
        
        # Business domains
        business_domains = [
            "gmail.com", "outlook.com", "yahoo.com", "company.com",
            "noreply", "no-reply", "support", "billing", "reports"
        ]
        
        if any(biz_domain in domain for biz_domain in business_domains[:3]):
            return "external"
        elif any(keyword in sender_email.lower() for keyword in ["noreply", "support", "billing"]):
            return "automated"
        else:
            return "business"

    def _extract_email_address(self, sender: str) -> str:
        """Extract raw email from 'Name <email@domain>' or return input if already email."""
        if not sender:
            return ""
        match = re.search(r"<([^>]+)>", sender)
        if match:
            return match.group(1).strip()
        return sender.strip()
    
    def create_draft(self, original_message_id: int, user_instructions: str = "",
                    tone: str = "professional", length: str = "medium") -> Dict[str, Any]:
        """
        Main entry point for creating email drafts
        
        Args:
            original_message_id: Database ID of email to reply to
            user_instructions: User's specific instructions for the reply
            tone: Tone of the draft (formal, professional, casual, friendly)
            length: Length of the draft (short, medium, detailed)
            
        Returns:
            Dict: Draft creation results and metadata
        """
        logger.info(f"Creating draft for message {original_message_id}")
        
        # Create initial state
        preferences = DraftPreferences(
            tone=DraftTone(tone),
            length=DraftLength(length),
            include_greeting=True,
            include_closing=True
        )
        
        initial_state = DraftState(
            original_message_id=original_message_id,
            user_instructions=user_instructions,
            draft_type=DraftType.REPLY,
            preferences=preferences
        )
        
        # Run the workflow
        final_state = self.workflow.invoke(initial_state)
        
        # LangGraph may return dict-like state; support both dict and dataclass access.
        def sget(key: str):
            if isinstance(final_state, dict):
                return final_state.get(key)
            return getattr(final_state, key, None)
        
        approval_status = sget("approval_status")
        safety_check = sget("safety_check")
        errors = sget("errors") or []
        
        # Return results
        return {
            "success": len(errors) == 0,
            "draft_id": sget("draft_id"),
            "draft_text": sget("generated_draft") or "",
            "draft_subject": sget("draft_subject") or "",
            "approval_status": approval_status.value if hasattr(approval_status, "value") else str(approval_status),
            "safety_check": {
                "is_safe": getattr(safety_check, "is_safe", True),
                "flagged_content": getattr(safety_check, "flagged_content", []),
                "recommendations": getattr(safety_check, "recommendations", [])
            },
            "processing_time": round(float(sget("processing_time") or 0), 3),
            "metadata": sget("draft_metadata") or {},
            "errors": errors
        }

def main():
    """
    Test function for email draft workflow
    Tests draft generation for sample emails
    """
    print("✍️ Testing Email Draft Workflow")
    print("=" * 60)
    
    try:
        # Initialize draft workflow
        draft_workflow = EmailDraftWorkflow()
        print("✅ Email draft workflow initialized successfully")
        
        # Resolve a real test message id from database instead of hardcoding.
        preferred_sender = os.getenv("TEST_SENDER_EMAIL", "noreply@phonepe.com")
        test_message_id = None
        with psycopg2.connect(**draft_workflow.db_params) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id
                    FROM email_messages
                    WHERE lower(sender_email) = lower(%s)
                    ORDER BY date_sent DESC
                    LIMIT 1
                """, (preferred_sender,))
                row = cur.fetchone()
                if row:
                    test_message_id = row[0]
                else:
                    cur.execute("""
                        SELECT id
                        FROM email_messages
                        ORDER BY date_sent DESC
                        LIMIT 1
                    """)
                    row = cur.fetchone()
                    if row:
                        test_message_id = row[0]

        if not test_message_id:
            print("❌ No email_messages found to run draft workflow test.")
            return
        print(f"🔎 Using test message ID: {test_message_id} (sender preference: {preferred_sender})")
        
        print(f"\n📝 Test 1: Professional Reply")
        print("-" * 40)
        
        # Test professional reply
        result1 = draft_workflow.create_draft(
            original_message_id=test_message_id,
            user_instructions="Thank them for their email and provide a helpful response",
            tone="professional",
            length="medium"
        )
        
        print(f"Success: {result1['success']}")
        print(f"Draft ID: {result1['draft_id']}")
        print(f"Safety Check: {'✅ Passed' if result1['safety_check']['is_safe'] else '⚠️ Issues found'}")
        print(f"Processing Time: {result1['processing_time']}s")
        print(f"Subject: {result1['draft_subject']}")
        print(f"\nDraft Preview:\n{result1['draft_text'][:200]}...")
        
        if result1['safety_check']['flagged_content']:
            print(f"⚠️ Safety Issues: {result1['safety_check']['flagged_content']}")
        
        if result1['errors']:
            print(f"❌ Errors: {result1['errors']}")
        
        print(f"\n📝 Test 2: Casual Reply")
        print("-" * 40)
        
        # Test casual reply
        result2 = draft_workflow.create_draft(
            original_message_id=test_message_id,
            user_instructions="Write a friendly response agreeing with their suggestion",
            tone="casual",
            length="short"
        )
        
        print(f"Success: {result2['success']}")
        print(f"Tone: Casual")
        print(f"Length: Short")
        print(f"Draft Preview:\n{result2['draft_text'][:200]}...")
        
        print("\n🎉 Email draft workflow tests completed!")
        print("\n💡 Next steps:")
        print("1. Integrate with FastAPI endpoints")
        print("2. Create frontend interface for draft review")
        print("3. Add draft editing and revision features")
        print("4. Implement automated sending after approval")
        
    except Exception as e:
        print(f"❌ Draft workflow test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
