import { writable } from 'svelte/store';
import { agentTasks } from './tasks';
import type { AgentTask } from './tasks';

export const isRecording = writable(false);
export const recordingStartTime = writable<Date | null>(null);
export const isHighlighting = writable(false);

// Function to fetch and add detected tasks
export async function detectAndAddTasks(context: string) {
  try {
    const response = await fetch(`http://localhost:8000/api/tasks/detect?context=${encodeURIComponent(context)}`);
    
    if (!response.ok) {
      throw new Error('Failed to detect tasks');
    }
    
    const data = await response.json();
    
    // Add detected tasks to the store
    if (data.tasks && Array.isArray(data.tasks)) {
      data.tasks.forEach((task: any) => {
        agentTasks.addTask({
          title: task.title,
          description: task.description,
          category: task.category,
          priority: task.priority,
          parameters: task.parameters,
          workflowType: task.workflowType // Include workflowType from backend
        });
      });
    }
    
    return data.tasks;
  } catch (error) {
    console.error('Error detecting tasks:', error);
    return [];
  }
}
