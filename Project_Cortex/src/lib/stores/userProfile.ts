import { writable } from 'svelte/store';

export interface UserProfile {
  content_bg: string;
  info_source: string;
  occupation_type: string;
  personal_focus: string;
  summary_mode: string;
}

// Options for dropdown fields
export const contentBgOptions = ['工作', '社交', '成长'];
export const infoSourceOptions = ['虚拟屏幕录制', '线下录音', '多模态笔记'];
export const occupationTypeOptions = ['投资人', '律师', '记者', '产品经理', '医生'];
export const summaryModeOptions = ['简洁', '适中', '详细'];

// Create the writable store with default values
function createUserProfileStore() {
  const { subscribe, set, update } = writable<UserProfile>({
    content_bg: '',
    info_source: '',
    occupation_type: '',
    personal_focus: '',
    summary_mode: ''
  });

  return {
    subscribe,
    set,
    update,
    // Helper method to update a single field
    updateField: (field: keyof UserProfile, value: string) => {
      update(profile => ({
        ...profile,
        [field]: value
      }));
    },
    // Helper method to check if profile is complete
    isComplete: (profile: UserProfile): boolean => {
      return !!(
        profile.content_bg &&
        profile.info_source &&
        profile.occupation_type &&
        profile.personal_focus &&
        profile.summary_mode
      );
    },
    // Helper method to reset profile
    reset: () => {
      set({
        content_bg: '',
        info_source: '',
        occupation_type: '',
        personal_focus: '',
        summary_mode: ''
      });
    }
  };
}

export const userProfile = createUserProfileStore();

// Store for the generated prompt template (no localStorage persistence since we clear on refresh)
function createGeneratedPromptStore() {
  // Don't load from localStorage since we clear it on page refresh
  const { subscribe, set, update } = writable<string>('');
  
  return {
    subscribe,
    set: (value: string) => {
      // Still save to localStorage for the current session
      // but it will be cleared on next refresh
      if (typeof window !== 'undefined') {
        localStorage.setItem('generatedPrompt', value);
      }
      set(value);
    },
    update,
    clear: () => {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('generatedPrompt');
      }
      set('');
    }
  };
}

export const generatedPrompt = createGeneratedPromptStore();

// Store for tracking onboarding completion
export const onboardingCompleted = writable<boolean>(false);
