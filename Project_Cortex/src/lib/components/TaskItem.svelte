<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { slide } from 'svelte/transition';
  import type { AgentTask, TaskParameter } from '$lib/stores/tasks';
  import { t } from '$lib/stores/i18n';
  
  export let task: AgentTask;
  export let wasExecuted: boolean = false; // Passed from parent to track execution history
  
  // Helper to get translated parameter name
  function getParamName(name: string): string {
    const paramNames = $t.tasks.item.paramNames as Record<string, string>;
    return paramNames[name] || name;
  }
  
  const dispatch = createEventDispatcher();
  let isExpanded = false;
  let isEditing = false;
  
  // Pre-computed priority colors map for O(1) lookup
  const PRIORITY_COLORS: Record<string, string> = {
    high: 'text-red-700 bg-red-50 border-red-100 dark:text-red-400 dark:bg-red-900/20 dark:border-red-800/50',
    medium: 'text-amber-700 bg-amber-50 border-amber-100 dark:text-amber-400 dark:bg-amber-900/20 dark:border-amber-800/50',
    low: 'text-green-700 bg-green-50 border-green-100 dark:text-green-400 dark:bg-green-900/20 dark:border-green-800/50',
    default: 'text-gray-600 bg-gray-50 border-gray-200 dark:text-gray-400 dark:bg-gray-800 dark:border-gray-700'
  };
  
  // Computed values that only update when task changes
  $: priorityColor = PRIORITY_COLORS[task.priority || 'default'] || PRIORITY_COLORS.default;
  $: isCompleted = task.status === 'completed';
  $: isExecuting = task.status === 'executing';
  $: isApproved = task.status === 'approved';
  $: isFailed = task.status === 'failed';
  $: isPending = task.status === 'pending';
  $: isWorking = isExecuting || isApproved; // Show spinner during both states
  $: formattedTime = task.executedAt ? new Date(task.executedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
  
  // Collapse expanded sections when execution starts
  $: if (isWorking) {
    isExpanded = false;
    isEditing = false;
  }
  
  function handleApprove() {
    console.log('[TaskItem] handleApprove clicked for task:', task.id, task.title);
    dispatch('approve', task.id);
    console.log('[TaskItem] approve event dispatched');
  }
  
  function handleDeny() {
    dispatch('deny', task.id);
  }
  
  function handleParameterChange(param: TaskParameter, event: Event) {
    const target = event.target as HTMLInputElement | HTMLSelectElement;
    let value: string | number | boolean = target.value;
    
    // Convert value based on type
    if (param.type === 'number') {
      value = parseFloat(target.value);
    } else if (param.type === 'boolean') {
      value = (target as HTMLInputElement).checked;
    }
    
    dispatch('parameterChange', { 
      taskId: task.id, 
      paramName: param.name, 
      value 
    });
  }
  
  function toggleEdit() {
    isEditing = !isEditing;
    isExpanded = isEditing;
  }
</script>

<div 
  class="group relative liquid-card overflow-hidden transition-all duration-500 {isCompleted ? 'opacity-75' : ''}"
>
  <!-- Main Card Content -->
  <div class="p-4">
    <!-- Header Row -->
    <div class="flex items-start gap-3">
      <!-- Status Icon / Category Icon -->
      <div class="flex-shrink-0 mt-0.5">
        {#if isWorking}
          <div class="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-600 dark:text-blue-400 animate-pulse ring-1 ring-blue-500/20">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
        {:else if isCompleted}
          <div class="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center text-green-600 dark:text-green-400 ring-1 ring-green-500/20">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
        {:else if isFailed}
          <div class="w-8 h-8 rounded-full bg-red-500/10 flex items-center justify-center text-red-600 dark:text-red-400 ring-1 ring-red-500/20">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
        {:else}
          <div class="w-8 h-8 rounded-full bg-black/5 dark:bg-white/10 flex items-center justify-center text-gray-500 dark:text-gray-400 ring-1 ring-black/5 dark:ring-white/10">
            <!-- Category Icons -->
            {#if task.category === 'zoom'}
              <img src="/zoom.png" alt="Zoom" class="w-6 h-6" />
            {:else if task.category === 'feishu' || task.category === 'scheduling'}
              <img src="/lark.png" alt="Feishu" class="w-6 h-6" />
            {:else if task.category === 'email' || task.category === 'communication'}
              <img src="/mail.png" alt="Email" class="w-6 h-6" />
            {:else if task.category === 'docFeishu'}
              <img src="/feishudoc.png" alt="DocFeishu" class="w-5 h-5" />
            {:else}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            {/if}
          </div>
        {/if}
      </div>

      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between gap-2">
          <h3 class="font-medium text-gray-900 dark:text-gray-100 truncate pr-2">
            {task.title}
          </h3>
          {#if task.priority}
            <span class="flex-shrink-0 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded-full border {priorityColor}">
              {task.priority}
            </span>
          {/if}
        </div>
        
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
          {task.description}
        </p>

        {#if formattedTime}
          <p class="text-xs text-gray-400 dark:text-gray-500 mt-1.5 flex items-center gap-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {formattedTime}
          </p>
        {/if}
      </div>

      <!-- Edit Button (Only for pending) -->
      {#if isPending}
        <button
          on:click={toggleEdit}
          class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors opacity-0 group-hover:opacity-100 {isEditing ? 'opacity-100 bg-gray-100 dark:bg-gray-700' : ''}"
          title="{isEditing ? $t.tasks.item.closeParams : $t.tasks.item.editParams}"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {#if isEditing}
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
            {:else}
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            {/if}
          </svg>
        </button>
      {/if}
    </div>

  <!-- Status Messages -->
  {#if isWorking}
    <div class="mt-3 p-3 bg-blue-50/50 dark:bg-blue-900/10 rounded-xl border border-blue-100/50 dark:border-blue-800/30 animate-fade-in">
      <div class="flex items-center gap-3">
        <div class="relative flex h-4 w-4">
          <svg class="animate-spin h-4 w-4 text-blue-600 dark:text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
        <span class="text-xs font-medium text-blue-600 dark:text-blue-400">
          {#if task.category === 'feishu' || task.category === 'scheduling'}
            {$t.tasks.item.agentExecuting.replace('{agent}', 'Feishu')}
          {:else if task.category === 'zoom'}
            {$t.tasks.item.agentExecuting.replace('{agent}', 'Zoom')}
          {:else if task.category === 'email' || task.category === 'communication'}
            {$t.tasks.item.agentExecuting.replace('{agent}', 'Email')}
          {:else if task.category === 'docFeishu'}
            {$t.tasks.item.agentExecuting.replace('{agent}', 'DocFeishu')}
          {:else}
            {$t.tasks.item.aiExecuting}
          {/if}
        </span>
      </div>
    </div>
  {:else if isCompleted && wasExecuted}
    <div class="mt-3 p-2 bg-green-50/50 dark:bg-green-900/10 rounded-xl border border-green-100/50 dark:border-green-800/30 flex items-center gap-2 animate-pop-in">
      <svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
      </svg>
      <span class="text-xs font-medium text-green-600 dark:text-green-400">{$t.tasks.item.taskCompleted}</span>
    </div>
  {:else if isFailed && wasExecuted}
      <div class="mt-3 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-2 rounded-lg border border-red-100 dark:border-red-800/30">
        {$t.tasks.item.error}: {task.error}
      </div>
    {/if}

    <!-- Parameters Section -->
    {#if isExpanded || isEditing}
      <div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700/50" transition:slide={{ duration: 200 }}>
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{$t.tasks.item.parameters}</h4>
        </div>
        <div class="space-y-2">
          {#each task.parameters as param}
            <div class="group/param">
              <div class="flex items-center gap-2 mb-1">
                <label for={`param-${task.id}-${param.name}`} class="text-xs font-medium text-gray-700 dark:text-gray-300">
                  {getParamName(param.name)}
                  {#if param.required}<span class="text-red-500">*</span>{/if}
                </label>
                {#if param.description}
                  <span class="text-[10px] text-gray-400 cursor-help" title={param.description}>ⓘ</span>
                {/if}
              </div>
              
              {#if isEditing}
                {#if param.type === 'select' && param.options}
                  <select
                    id={`param-${task.id}-${param.name}`}
                    value={param.value}
                    on:change={(e) => handleParameterChange(param, e)}
                    class="w-full px-2 py-1.5 text-xs bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow"
                    disabled={!isPending}
                  >
                    {#each param.options as option}
                      <option value={option}>{option}</option>
                    {/each}
                  </select>
                {:else if param.type === 'boolean'}
                  <div class="flex items-center gap-2">
                    <input
                      id={`param-${task.id}-${param.name}`}
                      type="checkbox"
                      checked={Boolean(param.value)}
                      on:change={(e) => handleParameterChange(param, e)}
                      class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      disabled={!isPending}
                    />
                    <span class="text-xs text-gray-600 dark:text-gray-400">{param.value ? $t.tasks.item.enabled : $t.tasks.item.disabled}</span>
                  </div>
                {:else if param.type === 'number'}
                  <input
                    id={`param-${task.id}-${param.name}`}
                    type="number"
                    value={param.value}
                    on:input={(e) => handleParameterChange(param, e)}
                    class="w-full px-2 py-1.5 text-xs bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow"
                    disabled={!isPending}
                  />
                {:else}
                  <input
                    id={`param-${task.id}-${param.name}`}
                    type="text"
                    value={param.value}
                    on:input={(e) => handleParameterChange(param, e)}
                    class="w-full px-2 py-1.5 text-xs bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 transition-shadow"
                    disabled={!isPending}
                  />
                {/if}
              {:else}
                <div class="px-2 py-1.5 bg-gray-50 dark:bg-gray-900/50 rounded border border-gray-100 dark:border-gray-800 text-xs text-gray-600 dark:text-gray-300 font-mono break-all">
                  {String(param.value)}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
  
  <!-- Action Buttons (Footer) -->
  {#if isPending}
    <div class="border-t border-white/20 dark:border-white/5 bg-white/10 dark:bg-black/20 px-4 py-2 flex gap-2 backdrop-blur-sm">
      <button
        on:click={handleApprove}
        class="flex-1 btn-primary btn-sm rounded-lg relative overflow-hidden group/btn"
      >
        <span class="relative z-10 flex items-center justify-center gap-2">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {$t.tasks.item.execute}
        </span>
        <div class="absolute inset-0 bg-white/20 translate-y-full group-hover/btn:translate-y-0 transition-transform duration-300"></div>
      </button>
      <button
        on:click={handleDeny}
        class="btn-secondary btn-sm bg-transparent border-white/30 hover:bg-white/20 backdrop-blur-sm hover:text-red-500 hover:border-red-200 transition-colors"
      >
        {$t.tasks.item.ignore}
      </button>
    </div>
  {/if}
</div>