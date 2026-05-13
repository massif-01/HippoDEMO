"""
================================================================================
DIFY TASK EXECUTION SERVICE
================================================================================

This module handles the execution of tasks using Dify workflow applications.
It provides functions to execute different types of tasks based on the Dify APIs.

================================================================================
"""

import httpx
import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
import uuid
from enum import Enum

from dify_config import (
    DIFY_BASE_URL,
    DIFY_WORKFLOW_KEYS,
    get_dify_headers,
    get_endpoint,
    validate_dify_config
)

# ============================================================================
# TASK TYPES
# ============================================================================

class TaskType(Enum):
    """Enumeration of supported task types"""
    PROMPT_GENERATION = "prompt_generation"
    INSIGHT_GENERATION = "insight_generation"
    EMAIL_SENDING = "email_sending"
    FEISHU_TODO = "feishu_todo"
    FEISHU_SCHEDULE = "feishu_schedule"
    GENERIC = "generic"

# ============================================================================
# TASK EXECUTION SERVICE
# ============================================================================

class DifyTaskService:
    """Service for executing tasks through Dify workflows"""
    
    def __init__(self):
        """Initialize the Dify task service"""
        self.client = httpx.AsyncClient(timeout=120.0)
        
        # Validate configuration on initialization
        is_valid, error = validate_dify_config()
        if not is_valid:
            raise ValueError(f"Invalid Dify configuration: {error}")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def determine_task_type(self, title: str, parameters: List[Dict]) -> TaskType:
        """
        Determine the type of task based on title and parameters
        
        Args:
            title: Task title
            parameters: Task parameters
        
        Returns:
            TaskType enum value
        """
        title_lower = title.lower()
        
        if any(keyword in title_lower for keyword in ["email", "mail", "send message"]):
            return TaskType.EMAIL_SENDING
        elif any(keyword in title_lower for keyword in ["schedule", "meeting", "calendar", "飞书"]):
            return TaskType.FEISHU_SCHEDULE
        elif any(keyword in title_lower for keyword in ["todo", "task list", "to-do", "任务"]):
            return TaskType.FEISHU_TODO
        elif any(keyword in title_lower for keyword in ["insight", "analysis", "洞察"]):
            return TaskType.INSIGHT_GENERATION
        elif any(keyword in title_lower for keyword in ["prompt", "suggestion", "提示"]):
            return TaskType.PROMPT_GENERATION
        else:
            return TaskType.GENERIC
    
    async def execute_task(
        self,
        task_id: str,
        title: str,
        parameters: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a task using the appropriate Dify workflow
        
        Args:
            task_id: Unique task identifier
            title: Task title
            parameters: Task parameters
            context: Optional context from screen recording
        
        Returns:
            Task execution result
        """
        task_type = self.determine_task_type(title, parameters)
        
        print(f"\n{'='*60}")
        print(f"DIFY TASK EXECUTION")
        print(f"Task ID: {task_id}")
        print(f"Title: {title}")
        print(f"Type: {task_type.value}")
        print(f"{'='*60}\n")
        
        try:
            if task_type == TaskType.EMAIL_SENDING:
                result = await self._execute_email_task(parameters, context)
            elif task_type == TaskType.FEISHU_TODO:
                result = await self._execute_feishu_todo_task(context or self._extract_context_from_params(parameters))
            elif task_type == TaskType.FEISHU_SCHEDULE:
                # Extract contact_person from parameters (参会人 field)
                params_dict = {p.get("name"): p.get("value") for p in parameters}
                contact_person = params_dict.get("参会人", "") or params_dict.get("contact_person", "")
                result = await self._execute_feishu_schedule_task(context or self._extract_context_from_params(parameters), contact_person)
            elif task_type == TaskType.INSIGHT_GENERATION:
                result = await self._execute_insight_task(parameters, context)
            elif task_type == TaskType.PROMPT_GENERATION:
                result = await self._execute_prompt_generation_task(parameters, context)
            else:
                result = await self._execute_generic_task(title, parameters, context)
            
            return {
                "taskId": task_id,
                "status": "completed",
                "result": result,
                "executedAt": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error executing task: {str(e)}")
            return {
                "taskId": task_id,
                "status": "failed",
                "error": str(e),
                "executedAt": datetime.now().isoformat()
            }
    
    def _extract_context_from_params(self, parameters: List[Dict]) -> str:
        """Extract context from parameters"""
        params_dict = {p.get("name"): p.get("value") for p in parameters}
        
        # Try to build context from various parameter names
        context_parts = []
        for key in ["content", "description", "context", "body", "text", "details"]:
            if key in params_dict and params_dict[key]:
                context_parts.append(str(params_dict[key]))
        
        return "\n".join(context_parts) if context_parts else "No context provided"
    
    async def _execute_email_task(self, parameters: List[Dict], context: Optional[str]) -> Dict[str, Any]:
        """
        Execute email sending task using Dify email workflow
        """
        params_dict = {p.get("name"): p.get("value") for p in parameters}
        
        # Prepare insight input (email content)
        insight_input = f"""
        To: {params_dict.get('recipient', 'Not specified')}
        Subject: {params_dict.get('subject', 'No subject')}
        
        {params_dict.get('body', context or 'No content provided')}
        """
        
        # Call Dify email workflow
        response = await self._call_workflow(
            workflow_key="email_app",
            inputs={
                "insight_input": insight_input,
                "theme_input": params_dict.get('subject', 'Email from RMinte')
            },
            response_mode="blocking"
        )
        
        if response.get("data", {}).get("status") == "succeeded":
            outputs = response.get("data", {}).get("outputs", {})
            return {
                "success": True,
                "message": "Email sent successfully via Dify",
                "details": {
                    "mail_output": outputs.get("mail_output", "Email content generated"),
                    "workflow_run_id": response.get("workflow_run_id"),
                    "sentAt": datetime.now().isoformat()
                }
            }
        else:
            raise Exception(f"Email workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
    
    async def _execute_feishu_todo_task(self, context: str) -> Dict[str, Any]:
        """
        Execute Feishu todo generation task
        """
        # Call Dify Feishu todo generator workflow (using demo version)
        response = await self._call_workflow(
            workflow_key="feishu_todo_demo",
            inputs={
                "context_input": context
            },
            response_mode="blocking"
        )
        
        if response.get("data", {}).get("status") == "succeeded":
            outputs = response.get("data", {}).get("outputs", {})
            return {
                "success": True,
                "message": "Todo list generated successfully",
                "details": {
                    "todos": outputs.get("todo", []),
                    "workflow_run_id": response.get("workflow_run_id"),
                    "createdAt": datetime.now().isoformat()
                }
            }
        else:
            raise Exception(f"Todo workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
    
    async def _execute_feishu_schedule_task(self, context: str, contact_person: str = "") -> Dict[str, Any]:
        """
        Execute Feishu schedule task
        """
        # Call Dify Feishu schedule executor workflow
        response = await self._call_workflow(
            workflow_key="feishu_executor",
            inputs={
                "context_input": context,
                "contact_person": contact_person  # Phone numbers separated by comma
            },
            response_mode="blocking"
        )
        
        if response.get("data", {}).get("status") == "succeeded":
            return {
                "success": True,
                "message": "Schedule created in Feishu successfully",
                "details": {
                    "workflow_run_id": response.get("workflow_run_id"),
                    "executedAt": datetime.now().isoformat()
                }
            }
        else:
            raise Exception(f"Schedule workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
    
    async def _execute_insight_task(self, parameters: List[Dict], context: Optional[str]) -> Dict[str, Any]:
        """
        Execute insight generation task
        """
        params_dict = {p.get("name"): p.get("value") for p in parameters}
        
        # First generate prompt if needed
        prompt_output = params_dict.get("prompt", "")
        if not prompt_output and context:
            # Generate prompt using prompt generator
            prompt_response = await self._execute_prompt_generation_task(parameters, context)
            prompt_output = prompt_response.get("details", {}).get("prompt_output", "")
        
        # Generate insight (updated to use prompt_input instead of prompt_output)
        response = await self._call_workflow(
            workflow_key="insight_app",
            inputs={
                "prompt_input": prompt_output or "Generate comprehensive insights",
                "context_input": context or self._extract_context_from_params(parameters)
            },
            response_mode="blocking"
        )
        
        if response.get("data", {}).get("status") == "succeeded":
            outputs = response.get("data", {}).get("outputs", {})
            return {
                "success": True,
                "message": "Insight generated successfully",
                "details": {
                    "insight_output": outputs.get("insight_output", ""),
                    "insight_title": outputs.get("insight_title", ""),
                    "insight_description": outputs.get("insight_description", ""),
                    "workflow_run_id": response.get("workflow_run_id")
                }
            }
        else:
            raise Exception(f"Insight workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
    
    async def _execute_prompt_generation_task(self, parameters: List[Dict], context: Optional[str]) -> Dict[str, Any]:
        """
        Execute prompt generation task
        """
        params_dict = {p.get("name"): p.get("value") for p in parameters}
        
        # Call Dify prompt generator workflow
        response = await self._call_workflow(
            workflow_key="prompt_generator",
            inputs={
                "content_bg": params_dict.get("content_bg", "工作"),  # Work, Social, Growth
                "info_source": params_dict.get("info_source", "虚拟屏幕录制"),  # Virtual screen recording
                "occupation_type": params_dict.get("occupation_type", "产品经理"),  # Product Manager
                "personal_focus": params_dict.get("personal_focus", context or "General productivity"),
                "summary_mode": params_dict.get("summary_mode", "适中")  # Moderate
            },
            response_mode="blocking"
        )
        
        if response.get("data", {}).get("status") == "succeeded":
            outputs = response.get("data", {}).get("outputs", {})
            return {
                "success": True,
                "message": "Prompt generated successfully",
                "details": {
                    "prompt_output": outputs.get("prompt_output", ""),
                    "workflow_run_id": response.get("workflow_run_id")
                }
            }
        else:
            raise Exception(f"Prompt generation failed: {response.get('data', {}).get('error', 'Unknown error')}")
    
    async def _execute_generic_task(self, title: str, parameters: List[Dict], context: Optional[str]) -> Dict[str, Any]:
        """
        Execute a generic task (fallback for unknown task types)
        """
        # For generic tasks, we'll try to use the insight generation workflow
        return await self._execute_insight_task(parameters, context)
    
    async def _call_workflow(
        self,
        workflow_key: str,
        inputs: Dict[str, Any],
        response_mode: str = "blocking",
        user: str = "rminte-user"
    ) -> Dict[str, Any]:
        """
        Call a Dify workflow API
        
        Args:
            workflow_key: Key identifying the workflow (e.g., 'email_app', 'feishu_todo')
            inputs: Input parameters for the workflow
            response_mode: 'blocking' or 'streaming'
            user: User identifier
        
        Returns:
            Workflow execution response
        """
        endpoint = get_endpoint("workflow_run")
        headers = get_dify_headers(workflow_key)
        
        payload = {
            "inputs": inputs,
            "response_mode": response_mode,
            "user": user
        }
        
        print(f"Calling Dify workflow: {workflow_key}")
        print(f"Endpoint: {endpoint}")
        print(f"Inputs: {json.dumps(inputs, indent=2, ensure_ascii=False)}")
        
        response = await self.client.post(
            endpoint,
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"Workflow API error: {response.status_code} - {response.text}")
        
        return response.json()
    
    async def call_workflow_streaming(
        self,
        workflow_key: str,
        inputs: Dict[str, Any],
        user: str = "rminte-user"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call a Dify workflow API with streaming response
        
        Args:
            workflow_key: Key identifying the workflow
            inputs: Input parameters for the workflow
            user: User identifier
        
        Yields:
            Streaming response chunks
        """
        endpoint = get_endpoint("workflow_run")
        headers = get_dify_headers(workflow_key)
        
        payload = {
            "inputs": inputs,
            "response_mode": "streaming",
            "user": user
        }
        
        async with self.client.stream(
            "POST",
            endpoint,
            headers=headers,
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield data
                    except json.JSONDecodeError:
                        continue

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def execute_dify_task(
    task_id: str,
    title: str,
    parameters: List[Dict[str, Any]],
    context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to execute a task using Dify workflows
    
    Args:
        task_id: Unique task identifier
        title: Task title
        parameters: Task parameters
        context: Optional context from screen recording
    
    Returns:
        Task execution result
    """
    async with DifyTaskService() as service:
        return await service.execute_task(task_id, title, parameters, context)

# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test the service
    async def test_service():
        """Test the Dify task service"""
        
        # Test email task
        email_result = await execute_dify_task(
            task_id="test-001",
            title="Send Email",
            parameters=[
                {"name": "recipient", "value": "test@example.com"},
                {"name": "subject", "value": "Test Email"},
                {"name": "body", "value": "This is a test email from Dify integration"}
            ]
        )
        print("Email Result:", json.dumps(email_result, indent=2))
        
        # Test todo task
        todo_result = await execute_dify_task(
            task_id="test-002",
            title="Create Todo List",
            parameters=[],
            context="Need to review project proposal, schedule team meeting, and update documentation"
        )
        print("Todo Result:", json.dumps(todo_result, indent=2))
    
    # Run the test
    asyncio.run(test_service())
