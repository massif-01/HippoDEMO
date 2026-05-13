<script lang="ts">
  import { apiConfig } from '$lib/stores/config';
  import { onMount } from 'svelte';
  import { t } from '$lib/stores/i18n';

  export let open = false;

  let endpoint = '';
  let apiKey = '';
  let model = '';

  onMount(() => {
    apiConfig.load();
    const unsubscribe = apiConfig.subscribe(config => {
      endpoint = config.endpoint;
      apiKey = config.apiKey;
      model = config.model;
    });

    return unsubscribe;
  });

  function saveSettings() {
    apiConfig.set({ endpoint, apiKey, model });
    open = false;
  }

  function close() {
    open = false;
  }

  function handleBackdropKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      close();
    }
  }
</script>

{#if open}
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div 
    class="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 transition-all duration-300"
    on:click={close}
    on:keydown={handleBackdropKeyDown}
  >
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div 
      class="liquid-modal p-8 max-w-md w-full mx-4 animate-fade-in"
      on:click|stopPropagation
    >
      <h3 class="text-2xl font-bold text-gray-900 dark:text-white mb-6 bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-300">{$t.settings.apiSettings}</h3>
      
      <div class="space-y-5">
        <div>
          <label for="endpoint" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            {$t.settings.apiEndpoint}
          </label>
          <input
            id="endpoint"
            type="url"
            bind:value={endpoint}
            placeholder={$t.settings.endpointPlaceholder || "https://api.openai.com/v1"}
            class="input-field"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-2 ml-1">
            {$t.settings.endpointHelp}
          </p>
        </div>

        <div>
          <label for="apikey" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            {$t.settings.apiKey}
          </label>
          <input
            id="apikey"
            type="password"
            bind:value={apiKey}
            placeholder={$t.settings.keyPlaceholder || "sk-..."}
            class="input-field"
          />
        </div>

        <div>
          <label for="model" class="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            {$t.settings.modelName}
          </label>
          <input
            id="model"
            type="text"
            bind:value={model}
            placeholder={$t.settings.modelPlaceholder || "gpt-3.5-turbo"}
            class="input-field"
          />
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-2 ml-1">
            {$t.settings.modelHelp}
          </p>
        </div>
      </div>

      <div class="flex gap-4 mt-8">
        <button on:click={close} class="btn-secondary flex-1">
          {$t.settings.cancel}
        </button>
        <button on:click={saveSettings} class="btn-primary flex-1 shadow-lg shadow-blue-500/30">
          {$t.settings.save}
        </button>
      </div>
    </div>
  </div>
{/if}
