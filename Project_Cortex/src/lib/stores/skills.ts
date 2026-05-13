import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';

export interface LearnedSkill {
  id: string;
  name: string;
  description: string;
  content: string;
  learnedAt: Date;
}

interface SerializedSkill {
  id: string;
  name: string;
  description: string;
  content: string;
  learnedAt: string;
}

const STORAGE_KEY = 'learnedSkills';

function deserializeSkills(raw: string): LearnedSkill[] {
  try {
    const parsed: SerializedSkill[] = JSON.parse(raw);
    return parsed.map(s => ({ ...s, learnedAt: new Date(s.learnedAt) }));
  } catch {
    return [];
  }
}

function serializeSkills(skills: LearnedSkill[]): string {
  return JSON.stringify(
    skills.map(s => ({ ...s, learnedAt: s.learnedAt.toISOString() }))
  );
}

function createSkillsStore() {
  const initial: LearnedSkill[] = [];
  const { subscribe, set, update } = writable<LearnedSkill[]>(initial);

  function persist(skills: LearnedSkill[]) {
    if (browser) {
      localStorage.setItem(STORAGE_KEY, serializeSkills(skills));
    }
  }

  return {
    subscribe,

    load() {
      if (browser) {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          set(deserializeSkills(raw));
        }
      }
    },

    addSkills(newSkills: Omit<LearnedSkill, 'id' | 'learnedAt'>[]) {
      update(current => {
        const additions: LearnedSkill[] = newSkills.map(s => ({
          ...s,
          description: s.description || '',
          id: crypto.randomUUID(),
          learnedAt: new Date()
        }));
        const updated = [...current, ...additions];
        persist(updated);
        return updated;
      });
    },

    removeSkill(id: string) {
      update(current => {
        const updated = current.filter(s => s.id !== id);
        persist(updated);
        return updated;
      });
    },

    clearSkills() {
      set([]);
      if (browser) {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
  };
}

export const learnedSkills = createSkillsStore();

export const skillsCount = derived(learnedSkills, $skills => $skills.length);

export const newSkillsAlert = writable<number>(0);
