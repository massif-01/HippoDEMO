import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export interface APIConfig {
  endpoint: string;
  apiKey: string;
  model: string;
}

const defaultConfig: APIConfig = {
  endpoint: 'https://api.openai.com/v1',
  apiKey: '',
  model: 'gpt-3.5-turbo'
};

function createConfigStore() {
  const { subscribe, set, update } = writable<APIConfig>(defaultConfig);

  return {
    subscribe,
    set: (config: APIConfig) => {
      if (browser) {
        localStorage.setItem('apiConfig', JSON.stringify(config));
      }
      set(config);
    },
    load: () => {
      if (browser) {
        const saved = localStorage.getItem('apiConfig');
        if (saved) {
          set(JSON.parse(saved));
        }
      }
    }
  };
}

export const apiConfig = createConfigStore();
