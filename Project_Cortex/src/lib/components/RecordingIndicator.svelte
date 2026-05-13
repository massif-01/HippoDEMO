<script lang="ts">
  import { isRecording, recordingStartTime, isHighlighting } from '$lib/stores/recording';
  import { onMount, onDestroy } from 'svelte';
  import { t } from '$lib/stores/i18n';

  let duration = '00:00';
  let interval: NodeJS.Timeout;

  function updateDuration() {
    if ($recordingStartTime) {
      const diff = Date.now() - $recordingStartTime.getTime();
      const minutes = Math.floor(diff / 60000);
      const seconds = Math.floor((diff % 60000) / 1000);
      duration = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
  }

  $: if ($isRecording && $recordingStartTime) {
    interval = setInterval(updateDuration, 1000);
  } else {
    clearInterval(interval);
    duration = '00:00';
  }

  onDestroy(() => {
    clearInterval(interval);
  });
</script>

{#if $isRecording}
  <div class="fixed top-4 left-1/2 transform -translate-x-1/2 flex items-center gap-2 z-50">
    <div class="bg-red-500 text-white px-4 py-2 rounded-full flex items-center gap-3 shadow-lg">
      <span class="relative flex h-3 w-3">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
        <span class="relative inline-flex rounded-full h-3 w-3 bg-white"></span>
      </span>
      <span class="font-medium">{$t.tasks.recordingIndicator.recording}</span>
      <span class="font-mono text-sm bg-red-600 px-2 py-0.5 rounded">{duration}</span>
    </div>
    {#if $isHighlighting}
      <div class="bg-amber-500 text-white px-3 py-2 rounded-full flex items-center gap-2 shadow-lg animate-pulse">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
        <span class="text-sm font-medium">{$t.highlight?.active || 'Highlighting'}</span>
      </div>
    {/if}
  </div>
{/if}