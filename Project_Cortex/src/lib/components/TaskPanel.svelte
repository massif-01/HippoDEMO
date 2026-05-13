<script lang="ts">
  import { fade } from 'svelte/transition';
  import { get } from 'svelte/store';
  import { onDestroy } from 'svelte';
  import { agentTasks, pendingTasksCount, tasksByStatus, PRIORITY_ORDER } from '$lib/stores/tasks';
  import TaskItem from './TaskItem.svelte';
  import type { AgentTask } from '$lib/stores/tasks';
  import { throttle } from '$lib/utils/debounce';
  import { t } from '$lib/stores/i18n';
  
  type FilterType = 'all' | 'pending' | 'completed';
  let filter: FilterType = 'pending';
  let searchQuery = '';
  
  // Progressive rendering for staggered animation
  let visibleTaskIds = new Set<string>();
  let pendingTimeouts: ReturnType<typeof setTimeout>[] = [];
  let lastTaskIds: string[] = [];
  
  // Track recently completed tasks to keep them visible for animation
  let recentlyCompletedIds = new Set<string>();
  
  // Track tasks that have been executed (to persist across component remounts)
  let executedTaskIds = new Set<string>();
  
  // Track tasks currently in fade-out animation
  let fadingOutTaskIds = new Set<string>();
  
  // Schedule tasks to appear one by one
  function scheduleTaskAppearance(tasks: AgentTask[]) {
    // Get current task IDs
    const currentIds = tasks.map(t => t.id);
    const currentIdsStr = currentIds.join(',');
    const lastIdsStr = lastTaskIds.join(',');
    
    // Skip if nothing changed
    if (currentIdsStr === lastIdsStr) return;
    
    // Clear any pending timeouts
    pendingTimeouts.forEach(t => clearTimeout(t));
    pendingTimeouts = [];
    
    // Find truly new tasks (not in lastTaskIds)
    const newTasks = tasks.filter(t => !lastTaskIds.includes(t.id));
    
    // Update last task IDs
    lastTaskIds = currentIds;
    
    if (newTasks.length === 0) {
      // No new tasks, but filter might have changed - show all immediately
      visibleTaskIds = new Set(currentIds);
      return;
    }
    
    // For new tasks, schedule staggered appearance
    newTasks.forEach((task, index) => {
      const timeout = setTimeout(() => {
        visibleTaskIds = new Set([...visibleTaskIds, task.id]);
      }, index * 150); // 150ms stagger
      pendingTimeouts.push(timeout);
    });
  }
  
  // Cleanup on destroy
  onDestroy(() => {
    pendingTimeouts.forEach(t => clearTimeout(t));
  });
  
  // Throttled search to avoid filtering on every keystroke
  const throttledSearch = throttle((query: string) => {
    searchQuery = query;
  }, 150);
  
  // Compute filtered tasks
  $: filteredTasks = getFilteredTasks($agentTasks, filter, searchQuery);
  
  // Watch for changes in filteredTasks and schedule animations
  $: if (filteredTasks) {
    scheduleTaskAppearance(filteredTasks);
  }
  
  // Track executing tasks - persist this info for completion animation
  $: {
    for (const task of $agentTasks) {
      if (task.status === 'executing' || task.status === 'approved') {
        executedTaskIds.add(task.id);
      }
    }
  }
  
  // Handle task completion animation flow
  function handleTaskCompletion(taskId: string) {
    // Only animate if this task was actually executed
    if (!executedTaskIds.has(taskId)) return;
    
    // Start fade-out after showing completion message
    setTimeout(() => {
      fadingOutTaskIds.add(taskId);
      fadingOutTaskIds = fadingOutTaskIds; // Trigger reactivity
      
      // Remove from view after fade-out animation completes
      setTimeout(() => {
        recentlyCompletedIds.delete(taskId);
        visibleTaskIds.delete(taskId);
        fadingOutTaskIds.delete(taskId);
        executedTaskIds.delete(taskId);
        // Trigger reactivity
        visibleTaskIds = visibleTaskIds;
        fadingOutTaskIds = fadingOutTaskIds;
      }, 500); // 0.5s fade-out animation
    }, 1500); // 1.5s completion message display
  }
  
  function getFilteredTasks(tasks: AgentTask[], filterType: FilterType, query: string): AgentTask[] {
    // Early exit for empty tasks
    if (!tasks.length) {
      return [];
    }
    
    // Single-pass filter and collect
    const lowerQuery = query ? query.toLowerCase() : '';
    const result: AgentTask[] = [];
    
    for (const task of tasks) {
      // Apply status filter
      if (filterType === 'pending') {
        // Keep recently completed tasks visible for animation
        const isRecentlyCompleted = (task.status === 'completed' || task.status === 'failed') && 
                                     recentlyCompletedIds.has(task.id);
        // Include 'approved' status to prevent flickering during approval->execution transition
        const isPendingOrExecuting = task.status === 'pending' || task.status === 'approved' || task.status === 'executing';
        if (!isPendingOrExecuting && !isRecentlyCompleted) continue;
        
        // Track newly completed tasks and start animation flow
        if ((task.status === 'completed' || task.status === 'failed') && !recentlyCompletedIds.has(task.id)) {
          recentlyCompletedIds.add(task.id);
          handleTaskCompletion(task.id);
        }
      } else if (filterType === 'completed') {
        if (task.status !== 'completed' && task.status !== 'failed') continue;
      }
      
      // Apply search filter
      if (lowerQuery) {
        const titleMatch = task.title.toLowerCase().includes(lowerQuery);
        const descMatch = task.description.toLowerCase().includes(lowerQuery);
        const catMatch = task.category?.toLowerCase().includes(lowerQuery);
        if (!titleMatch && !descMatch && !catMatch) continue;
      }
      
      result.push(task);
    }
    
    // Sort in-place - use cached priority order
    result.sort((a, b) => {
      const pA = a.priority || 'undefined';
      const pB = b.priority || 'undefined';
      const priorityDiff = (PRIORITY_ORDER[pB] || 0) - (PRIORITY_ORDER[pA] || 0);
      
      if (priorityDiff !== 0) return priorityDiff;
      return b.createdAt.getTime() - a.createdAt.getTime();
    });
    
    return result;
  }
  
  // Check if a task is fading out
  function isTaskFadingOut(taskId: string): boolean {
    return fadingOutTaskIds.has(taskId);
  }
  
  function handleApprove(event: CustomEvent) {
    console.log('[TaskPanel] handleApprove called with:', event.detail);
    agentTasks.approveTask(event.detail);
  }
  
  function handleDeny(event: CustomEvent) {
    agentTasks.denyTask(event.detail);
  }
  
  function handleParameterChange(event: CustomEvent) {
    const { taskId, paramName, value } = event.detail;
    agentTasks.updateTaskParameter(taskId, paramName, value);
  }
  
  function clearAllTasks() {
    if (confirm($t.tasks.confirmClearAll)) {
      agentTasks.clearTasks();
    }
  }
  
  function clearCompletedTasks() {
    if (confirm($t.tasks.confirmClearCompleted)) {
      const currentTasks = get(agentTasks);
      agentTasks.setTasks(
        currentTasks.filter(t => !['completed', 'failed'].includes(t.status))
      );
    }
  }

  function handleExecuteAll() {
    if ($pendingTasksCount === 0) return;
    // Optional: Add confirmation dialog
    // if (confirm(`确定要执行所有 ${$pendingTasksCount} 个待处理任务吗？`)) {
    agentTasks.approveAllPendingTasks();
    // }
  }

  function setFilter(key: string) {
    filter = key as FilterType;
  }

  // Mock function to add sample tasks for testing
  function addSampleTask() {
    agentTasks.addTask({
      title: '发送邮件',
      description: '根据上下文编写并发送邮件',
      category: '通信',
      priority: 'high',
      parameters: [
        {
          name: 'recipient',
          value: 'john@example.com',
          type: 'text',
          description: '收件人电子邮件地址',
          required: true
        },
        {
          name: 'subject',
          value: '会议后续',
          type: 'text',
          description: '邮件主题',
          required: true
        },
        {
          name: 'body',
          value: '感谢您今天的会议...',
          type: 'text',
          description: '邮件正文内容',
          required: true
        },
        {
          name: 'priority',
          value: '普通',
          type: 'select',
          options: ['低', '普通', '高'],
          description: '邮件优先级'
        },
        {
          name: 'attachFiles',
          value: false,
          type: 'boolean',
          description: '附加上下文中的相关文件'
        }
      ]
    });
  }
</script>

<div class="h-full flex flex-col">
  <!-- Header -->
  <div class="panel-header">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-base font-semibold text-gray-900 dark:text-white tracking-tight flex items-center gap-2">
        <div class="p-1.5 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-blue-600 dark:text-blue-400">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        {$t.tasks.title}
      </h2>
      {#if $pendingTasksCount > 0}
        <span class="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-[10px] font-semibold uppercase tracking-wider rounded-full">
          {$pendingTasksCount} {$t.tasks.pending}
        </span>
      {/if}
    </div>
    
    <!-- Search bar -->
    <div class="relative mb-3 group">
      <input
        type="text"
        value={searchQuery}
        on:input={(e) => throttledSearch(e.currentTarget.value)}
        placeholder={$t.tasks.filter}
        class="w-full pl-9 pr-3 py-1.5 text-sm bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all placeholder-gray-400 dark:placeholder-gray-500"
      />
      <svg class="absolute left-3 top-2 w-4 h-4 text-gray-400 group-focus-within:text-blue-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    </div>
    
    <!-- Filter tabs -->
    <div class="flex p-1 bg-black/5 dark:bg-white/5 rounded-xl backdrop-blur-sm">
      {#each [['all', $t.tasks.tabs.all], ['pending', $t.tasks.tabs.pending], ['completed', $t.tasks.tabs.completed]] as [tabKey, tabLabel]}
        <button
          on:click={() => setFilter(tabKey)}
          class="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-300
            {filter === tabKey 
              ? 'bg-white dark:bg-white/10 text-gray-900 dark:text-white shadow-sm ring-1 ring-black/5 dark:ring-white/10' 
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5'}"
        >
          {tabLabel}
        </button>
      {/each}
    </div>
  </div>
  
  <!-- Task list -->
  <div class="flex-1 overflow-y-auto px-5 py-3 hide-scrollbar">
    {#if !filteredTasks.length}
      <div class="flex flex-col items-center justify-center h-full py-12 text-center">
        {#if filter === 'completed'}
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-50 dark:from-gray-800 dark:to-gray-900 flex items-center justify-center mb-3 shadow-inner">
            <svg class="w-6 h-6 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p class="text-sm font-medium text-gray-900 dark:text-gray-100">{$t.tasks.noHistory}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{$t.tasks.noHistoryDesc}</p>
        {:else}
          <div class="w-12 h-12 rounded-xl bg-gray-50 dark:bg-gray-800/50 flex items-center justify-center mb-3">
            <svg class="w-6 h-6 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
          </div>
          <p class="text-sm font-medium text-gray-900 dark:text-gray-100">
            {searchQuery ? $t.tasks.noMatch : $t.tasks.noTasks}
          </p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-[200px]">
            {filter === 'pending' ? $t.tasks.detecting : $t.tasks.startRecording}
          </p>
          
          {#if !searchQuery}
            <button
              on:click={addSampleTask}
              class="mt-4 px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 text-xs font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors shadow-sm"
            >
              {$t.tasks.addSample}
            </button>
          {/if}
        {/if}
      </div>
    {:else}
      <div class="space-y-3">
        {#each filteredTasks as task (task.id)}
          {#if visibleTaskIds.has(task.id)}
            <div 
              class="task-item-wrapper {isTaskFadingOut(task.id) ? 'task-fade-out' : ''}"
            >
              <TaskItem 
                {task}
                wasExecuted={executedTaskIds.has(task.id)}
                on:approve={handleApprove}
                on:deny={handleDeny}
                on:parameterChange={handleParameterChange}
              />
            </div>
          {/if}
        {/each}
      </div>
    {/if}
  </div>
  
  <!-- Footer actions -->
  {#if $agentTasks.length > 0}
    <div class="px-5 py-3 border-t border-white/20 dark:border-white/5 bg-white/5 dark:bg-black/20 backdrop-blur-md">
      <div class="flex gap-2 items-center justify-between">
        {#if filter === 'completed'}
          {#if $tasksByStatus.completed.length > 0 || $tasksByStatus.failed.length > 0}
            <button
              on:click={clearCompletedTasks}
              class="text-xs text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 font-medium transition-colors flex items-center gap-1"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              {$t.tasks.clearHistory}
            </button>
            <div class="flex gap-3 text-xs">
              {#if $tasksByStatus.completed.length > 0}
                <span class="text-green-600 dark:text-green-400 font-medium">{$tasksByStatus.completed.length} {$t.tasks.completedCount}</span>
              {/if}
              {#if $tasksByStatus.failed.length > 0}
                <span class="text-red-600 dark:text-red-400 font-medium">{$tasksByStatus.failed.length} {$t.tasks.failedCount}</span>
              {/if}
            </div>
          {:else}
            <span class="text-xs text-gray-400 w-full text-center">{$t.tasks.noRecords}</span>
          {/if}
        {:else}
          <button
            on:click={clearAllTasks}
            class="text-xs text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 font-medium transition-colors flex items-center gap-1"
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            {$t.tasks.clearAll}
          </button>
          <div class="flex items-center gap-3">
            {#if $tasksByStatus.executing.length > 0}
              <span class="text-xs text-blue-600 dark:text-blue-400 font-medium animate-pulse flex items-center gap-1">
                <svg class="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {$t.tasks.executing.replace('{count}', $tasksByStatus.executing.length.toString())}
              </span>
            {/if}
            
            {#if $pendingTasksCount > 0}
              <button 
                on:click={handleExecuteAll}
                class="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-all shadow-sm flex items-center gap-1.5 active:scale-95"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                {$t.tasks.executeAll.replace('{count}', $pendingTasksCount.toString())}
              </button>
            {:else}
              <span class="text-xs text-gray-500 dark:text-gray-400">0 {$t.tasks.pending}</span>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .hide-scrollbar {
    -ms-overflow-style: none;  /* IE and Edge */
    scrollbar-width: none;  /* Firefox */
  }
  .hide-scrollbar::-webkit-scrollbar {
    display: none;
  }
  
  /* Smooth task item appearance with slide-in effect */
  .task-item-wrapper {
    animation: task-slide-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  
  @keyframes task-slide-in {
    0% {
      opacity: 0;
      transform: translateY(15px) scale(0.96);
    }
    100% {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
</style>