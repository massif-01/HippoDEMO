<script lang="ts">
  import { onDestroy } from 'svelte';
  import { isRecording, recordingStartTime } from '$lib/stores/recording';
  import { promptSuggestions, promptSuggestionsLoading, userContext, recordingContexts } from '$lib/stores/chat';
  import { summaryFeed, summaryLoading } from '$lib/stores/summary';
  import { generatedPrompt, userProfile } from '$lib/stores/userProfile';
  import { agentTasks } from '$lib/stores/tasks';
  import { get } from 'svelte/store';
  import { t } from '$lib/stores/i18n';

  // --- API Endpoints ---
  // Proxied through Vite: /recording-api/* -> https://vlmac.xapp.aoseo.com/api/*
  const SCREEN_RECORDING_API = '/recording-api';  // Video processing backend (API A)
  const API_B_URL = 'http://localhost:8000';         // Task polling during recording

  let abortController: AbortController | null = null;
  let taskPollingInterval: ReturnType<typeof setInterval> | null = null;

  // --- Task Polling (API B) during recording ---
  function startTaskPolling() {
    stopTaskPolling();
    pollTasks();
    taskPollingInterval = setInterval(pollTasks, 300_000);
  }

  function stopTaskPolling() {
    if (taskPollingInterval) {
      clearInterval(taskPollingInterval);
      taskPollingInterval = null;
    }
  }

  async function pollTasks() {
    try {
      const response = await fetch(`${API_B_URL}/api/tasks/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: 'start' })
      });

      if (!response.ok) return;

      const data = await response.json();
      if (!data.tasks?.length) return;

      data.tasks.forEach((task: any) => {
        const params = (task.parameters || []).map((p: any) => ({
          name: p.name || '',
          value: p.value || '',
          type: p.type || 'text',
          description: p.description,
          options: p.options,
          required: p.required !== false
        }));

        agentTasks.addTask({
          title: task.title || 'Untitled Task',
          description: task.description || '',
          category: task.category || 'general',
          priority: task.priority || 'medium',
          parameters: params,
          workflowType: task.workflowType
        });
      });
      console.log(`[Polling] Added ${data.tasks.length} tasks`);
    } catch (error) {
      console.error('[Polling] Task polling error:', error);
    }
  }

  // --- Stop Recording: concurrent fetches ---
  async function processRecordingStop() {
    const storedPromptTemplate = get(generatedPrompt);
    const currentProfile = get(userProfile);

    $summaryLoading = !!storedPromptTemplate;
    $promptSuggestionsLoading = !!(currentProfile?.content_bg && currentProfile?.occupation_type);

    if (abortController) abortController.abort();
    abortController = new AbortController();
    const signal = abortController.signal;

    const apiPromises: Promise<void>[] = [];

    // (a) Prompt suggestions from original API
    if (currentProfile?.content_bg && currentProfile?.occupation_type && currentProfile?.personal_focus) {
      apiPromises.push(
        fetch('http://localhost:8000/api/auto_suggestion', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content_bg: currentProfile.content_bg,
            occupation_type: currentProfile.occupation_type,
            personal_focus: currentProfile.personal_focus,
            context_input: ''
          }),
          signal
        })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            if (data.PromptSuggestion?.length) {
              $promptSuggestions = data.PromptSuggestion.map((s: any) => ({
                id: s.id || crypto.randomUUID(),
                text: s.text
              }));
            }
          }
        })
        .catch(e => { if (e.name !== 'AbortError') console.error('Suggestion error:', e); })
        .finally(() => { $promptSuggestionsLoading = false; })
      );
    }

    // (b) Context from MinIO via backend proxy (authenticated)
    apiPromises.push(
      fetch('http://localhost:8000/api/context/minio', {
        method: 'GET',
        signal
      })
      .then(async (res) => {
        if (res.ok) {
          const contextContent = await res.text();

          const newContext = {
            id: crypto.randomUUID(),
            content: contextContent,
            timestamp: new Date(),
            selected: true
          };

          recordingContexts.update(contexts => [
            ...contexts.map(ctx => ({ ...ctx, selected: false })),
            newContext
          ]);
          $userContext = contextContent;
        }
      })
      .catch(e => {
        if (e.name !== 'AbortError') console.error('Context error:', e);
      })
    );

    // (c) Summary / Insight from original API
    if (storedPromptTemplate) {
      apiPromises.push(
        fetch('http://localhost:8000/api/insight_app', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt_input: storedPromptTemplate,
            context_input: ''
          }),
          signal
        })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            if (data.insight_output) {
              $summaryFeed = { insights: data.insight_output, tasks: [] };
            }
          }
        })
        .catch(e => { if (e.name !== 'AbortError') console.error('Insight error:', e); })
        .finally(() => { $summaryLoading = false; })
      );
    }

    await Promise.allSettled(apiPromises);
  }

  // --- Main toggle handler ---
  async function toggleRecording() {
    const recording = $isRecording;

    try {
      if (!recording) {
        $summaryLoading = false;
        $promptSuggestionsLoading = false;

        console.log(`[${new Date().toISOString()}] Starting video processing...`);
        const response = await fetch(`${SCREEN_RECORDING_API}/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
          $isRecording = true;
          $recordingStartTime = new Date();
          startTaskPolling();
          console.log('Recording started successfully');
        } else {
          console.error('Failed to start recording:', response.statusText);
          alert('Failed to start recording. Please check if the video processing backend is running.');
        }
      } else {
        console.log(`[${new Date().toISOString()}] Stopping video processing...`);

        stopTaskPolling();

        const stopResponse = await fetch(`${SCREEN_RECORDING_API}/stop`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });

        if (!stopResponse.ok) {
          console.error('Failed to stop recording:', stopResponse.statusText);
        }

        $isRecording = false;
        $recordingStartTime = null;

        await processRecordingStop();
      }
    } catch (error) {
      console.error('Recording error:', error);
      stopTaskPolling();
      $isRecording = false;
      $recordingStartTime = null;
      alert('Recording service unavailable. Please ensure the video processing backend is running.');
    }
  }

  onDestroy(() => {
    stopTaskPolling();
    if (abortController) abortController.abort();
  });
</script>

<button
  on:click={toggleRecording}
  class="p-2 rounded-lg transition-all {$isRecording ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse' : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'}"
  title={$isRecording ? $t.chat.recording.stop : $t.chat.recording.start}
>
  {#if $isRecording}
    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  {:else}
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" stroke-width="2" />
      <circle cx="12" cy="12" r="3" fill="currentColor" />
    </svg>
  {/if}
</button>
