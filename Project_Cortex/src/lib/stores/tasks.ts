import { writable, derived, get } from 'svelte/store';

export interface TaskParameter {
  name: string;
  value: string | number | boolean;
  type: 'text' | 'number' | 'boolean' | 'select';
  description?: string;
  options?: string[]; // For select type
  required?: boolean;
}

export interface AgentTask {
  id: string;
  title: string;
  description: string;
  category?: string;
  priority?: 'low' | 'medium' | 'high';
  parameters: TaskParameter[];
  status: 'pending' | 'approved' | 'denied' | 'executing' | 'completed' | 'failed';
  createdAt: Date;
  executedAt?: Date;
  result?: any;
  error?: string;
  workflowType?: string; // Optional workflow type hint from backend
}

// Priority order map for sorting - cached to avoid recreation
const PRIORITY_ORDER: Record<string, number> = { high: 3, medium: 2, low: 1, undefined: 0 };

// Workflow type mapping - cached
const WORKFLOW_MAP: Record<string, string> = {
  email: 'email_executor',
  docFeishu: 'docFeishu_executor'
};

// Active AbortControllers for cancelling in-flight requests per task
const activeTaskControllers = new Map<string, AbortController>();

function createTaskStore() {
  const { subscribe, set, update } = writable<AgentTask[]>([]);

  // Execute a task by calling the backend
  async function executeTask(taskId: string) {
    console.log('[executeTask] Function called with taskId:', taskId);
    
    const tasks = get(agentTasks);
    const task = tasks.find(t => t.id === taskId);
    
    if (!task) {
      console.error('[executeTask] Task not found:', taskId);
      return;
    }
    
    console.log('[executeTask] Found task:', task);
    
    // Cancel any existing request for this specific task
    if (activeTaskControllers.has(taskId)) {
      activeTaskControllers.get(taskId)?.abort();
    }
    const controller = new AbortController();
    activeTaskControllers.set(taskId, controller);
    
    const executionTime = new Date();

    // Update status to executing - batch the date creation
    update(tasks => 
      tasks.map(t => 
        t.id === taskId 
          ? { ...t, status: 'executing', executedAt: executionTime } 
          : t
      )
    );

    try {
      // Determine workflow type - use cached map
      let workflowType = task.workflowType || 'feishu_executor';
      
      if (WORKFLOW_MAP[task.category || '']) {
        workflowType = WORKFLOW_MAP[task.category || ''];
      } else if (task.title.includes('邮件')) {
        workflowType = 'email_executor';
      }
      
      // Build context string once
      const paramString = task.parameters.map(p => `${p.name}: ${p.value}`).join(', ');
      
      // Structure the task data
      const taskData = {
        taskId: task.id,
        title: task.title,
        description: task.description,
        category: task.category || '',
        priority: task.priority || 'medium',
        parameters: task.parameters,
        context: {
          createdAt: task.createdAt.toISOString(),
          executedAt: executionTime.toISOString(),
          contextString: `任务: ${task.title}\n描述: ${task.description}\n优先级: ${task.priority || '普通'}\n参数: ${paramString}`
        },
        workflowType
      };

      console.log('[executeTask] Sending request to backend:', taskData);
      
      const response = await fetch('http://localhost:8000/api/tasks/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(taskData),
        signal: controller.signal
      });
      
      console.log('[executeTask] Response status:', response.status);

      if (!response.ok) {
        throw new Error(`Failed to execute task: ${response.statusText}`);
      }

      const result = await response.json();

      // Update task with success
      update(tasks => 
        tasks.map(t => 
          t.id === taskId 
            ? { ...t, status: 'completed', result } 
            : t
        )
      );

    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      // Update task with error
      update(tasks => 
        tasks.map(t => 
        t.id === taskId 
          ? { ...t, status: 'failed', error: error instanceof Error ? error.message : String(error) } 
          : t
        )
      );
    } finally {
      // Only remove if it's the same controller (hasn't been replaced by a new request)
      if (activeTaskControllers.get(taskId) === controller) {
        activeTaskControllers.delete(taskId);
      }
    }
  }

  return {
    subscribe,
    
    // Add a new task to the list
    addTask: (task: Omit<AgentTask, 'id' | 'createdAt' | 'status'>) => {
      update(tasks => [
        ...tasks,
        {
          ...task,
          id: crypto.randomUUID(),
          status: 'pending',
          createdAt: new Date(),
          workflowType: task.workflowType // Preserve workflowType if provided
        }
      ]);
    },

    // Update task parameters
    updateTaskParameters: (taskId: string, parameters: TaskParameter[]) => {
      update(tasks => 
        tasks.map(task => 
          task.id === taskId 
            ? { ...task, parameters } 
            : task
        )
      );
    },

    // Update a single parameter value
    updateTaskParameter: (taskId: string, paramName: string, value: any) => {
      update(tasks => 
        tasks.map(task => {
          if (task.id === taskId) {
            const updatedParams = task.parameters.map(param =>
              param.name === paramName 
                ? { ...param, value }
                : param
            );
            return { ...task, parameters: updatedParams };
          }
          return task;
        })
      );
    },

    // Approve and execute a task
    approveTask: async (taskId: string) => {
      console.log('[Tasks Store] approveTask called with taskId:', taskId);
      
      update(tasks => 
        tasks.map(task => 
          task.id === taskId 
            ? { ...task, status: 'approved' } 
            : task
        )
      );
      
      // Execute the task
      console.log('[Tasks Store] Calling executeTask...');
      await executeTask(taskId);
    },

    // Approve and execute all pending tasks
    approveAllPendingTasks: async () => {
      const tasks = get(agentTasks);
      const pendingTasks = tasks.filter(t => t.status === 'pending');
      
      if (pendingTasks.length === 0) return;

      console.log(`[Tasks Store] approveAllPendingTasks called for ${pendingTasks.length} tasks`);

      // Update all statuses to approved first
      update(currentTasks => 
        currentTasks.map(task => 
          task.status === 'pending'
            ? { ...task, status: 'approved' }
            : task
        )
      );

      // Execute all tasks concurrently
      // We don't await individual tasks here to let them run in parallel
      // but we wait for all to complete before returning
      await Promise.all(pendingTasks.map(task => executeTask(task.id)));
    },

    // Deny a task (remove from list immediately)
    denyTask: (taskId: string) => {
      update(tasks => tasks.filter(task => task.id !== taskId));
    },

    // Remove completed/denied tasks
    removeTask: (taskId: string) => {
      update(tasks => tasks.filter(task => task.id !== taskId));
    },

    // Clear all tasks
    clearTasks: () => set([]),

    // Set multiple tasks at once (e.g., from API)
    setTasks: (newTasks: AgentTask[]) => set(newTasks)
  };
}

// This function has been moved inside createTaskStore

export const agentTasks = createTaskStore();

// Derived store for pending tasks count - optimized with single pass
export const pendingTasksCount = derived(
  agentTasks,
  $tasks => {
    let count = 0;
    for (const t of $tasks) {
      if (t.status === 'pending') count++;
    }
    return count;
  }
);

// Derived store for tasks by status - single pass categorization
export const tasksByStatus = derived(
  agentTasks,
  $tasks => {
    const result = {
      pending: [] as AgentTask[],
      executing: [] as AgentTask[],
      completed: [] as AgentTask[],
      failed: [] as AgentTask[]
    };
    
    for (const task of $tasks) {
      if (task.status in result) {
        result[task.status as keyof typeof result].push(task);
      }
    }
    
    return result;
  }
);

// Export priority order for use in TaskPanel
export { PRIORITY_ORDER };
