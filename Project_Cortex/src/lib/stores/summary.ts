import { writable } from 'svelte/store';

export interface Task {
  id: string;
  text: string;
  completed: boolean;
}

export interface SummaryFeed {
  insights: string;
  tasks: Task[];
}

export const summaryFeed = writable<SummaryFeed | null>(null);
export const summaryLoading = writable<boolean>(false);
