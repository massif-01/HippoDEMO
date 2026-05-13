import { writable, derived } from 'svelte/store';

export type Language = 'zh' | 'en';

const storedLanguage = typeof window !== 'undefined' ? localStorage.getItem('language') as Language : 'zh';
export const currentLanguage = writable<Language>(storedLanguage || 'zh');

currentLanguage.subscribe(value => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('language', value);
  }
});

export const translations = {
  zh: {
    onboarding: {
      welcome: '欢迎使用 HippoGenius',
      subtitle: '首次使用需要设置您的个人偏好，系统将为您生成专属的智能分析模板',
      required: '必须完成此步骤才能开始使用',
      step1: '步骤 1 / 2',
      step1Title: '个人信息设置',
      step2: '步骤 2 / 2',
      step2Title: '提示模板生成完成',
      contentBg: '录制背景',
      infoSource: '信息来源',
      occupationType: '职业类型',
      personalFocus: '个人聚焦',
      remainingChars: '字符剩余',
      placeholderFocus: '请描述您的关注重点...',
      summaryMode: '总结深度',
      select: '请选择...',
      cancel: '取消',
      generating: '生成中...',
      start: '开始使用',
      templateGenerated: '✨ 您的个性化提示模板已生成',
      templateSubtitle: '基于您的职业背景和需求定制的智能分析框架',
      successMessage: '提示模板已成功生成！此模板将在您每次停止录制时自动应用，为您生成个性化的洞察分析。',
      copy: '复制模板',
      copied: '已复制',
      error: '生成提示词失败',
      emptyError: '后端返回空提示词',
      fallbackTemplate: '提示模板生成中，请稍候...',
      switchLang: 'Switch to English'
    },
    settings: {
      title: '个人设置',
      subtitle: '更新您的个人信息以获得更好的体验',
      success: '设置已成功更新！',
      update: '保存更改',
      updating: '更新中...',
      // API Settings
      apiSettings: 'API 设置',
      apiEndpoint: 'API 端点',
      apiKey: 'API 密钥',
      modelName: '模型名称',
      endpointHelp: '兼容 OpenAI 的 API 端点',
      modelHelp: '模型名称（例如：gpt-3.5-turbo, gpt-4）',
      cancel: '取消',
      save: '保存设置',
    },
    options: {
      contentBg: {
        '工作': '工作',
        '社交': '社交',
        '成长': '成长'
      },
      infoSource: {
        '虚拟屏幕录制': '虚拟屏幕录制',
        '线下录音': '线下录音',
        '多模态笔记': '多模态笔记'
      },
      occupationType: {
        '投资人': '投资人',
        '律师': '律师',
        '记者': '记者',
        '产品经理': '产品经理',
        '医生': '医生'
      },
      summaryMode: {
        '简洁': '简洁',
        '适中': '适中',
        '详细': '详细'
      }
    },
    chat: {
        howCanIHelp: '有什么可以帮助您的？',
        startPrompt: '开始录制或输入消息',
        inputPlaceholder: '请输入您的问题...',
        thinking: '思考中...',
        aiWarning: 'AI 可能会出错。请验证重要信息。',
        error: {
            auth: '身份验证失败。请在设置中检查您的 API 密钥。',
            notFound: '找不到 API 端点。请检查您的 API 配置。',
            rateLimit: '超出速率限制。请稍后再试。',
            network: '网络错误。请检查您的连接和 API 设置。',
            general: '错误',
            default: '抱歉，处理您的请求时出现错误。'
        },
        contextIntro: '您可以访问以下来自用户屏幕录制的上下文：\n\n{context}\n\n请使用此上下文提供更相关和具体的答案。',
        recording: {
            start: '开始录制',
            stop: '停止录制'
        },
        promptSuggestions: {
            select: '选择一个提示词建议...',
            loading: '正在生成提示词推荐...'
        },
        contextSelector: {
            title: '录制上下文',
            selectAll: '全选',
            clearAll: '清除全部'
        },
        message: {
            you: '您',
            assistant: '助手',
            usingContext: '使用屏幕上下文',
            copy: '复制',
            retry: '重试'
        },
        quickCommand: {
            hint: '按下',
            hintSuffix: '快速创建任务'
        }
    },
    summary: {
        title: '上下文洞察',
        loading: '正在分析屏幕内容...',
        keyInsights: '关键洞察',
        todoItems: '待办事项',
        waitingTitle: '等待上下文',
        waitingDesc: '开始录制您的屏幕以查看 AI 生成的洞察和任务。'
    },
    tasks: {
        title: '可执行任务',
        pending: '待处理',
        filter: '筛选任务...',
        tabs: {
            all: '全部',
            pending: '待处理',
            completed: '已完成'
        },
        noHistory: '暂无历史记录',
        noHistoryDesc: '已执行的任务将显示在这里',
        noTasks: '没有找到任务',
        noMatch: '没有匹配的任务',
        startRecording: '开始录制以检测可执行任务',
        detecting: '从您的屏幕检测到的任务将显示在这里',
        addSample: '添加示例任务',
        clearHistory: '清除历史',
        completedCount: '已完成',
        failedCount: '失败',
        noRecords: '无历史记录',
        clearAll: '清除全部',
        executing: '运行中',
        executeAll: '一键执行',
        confirmClearAll: '您确定要清除所有任务吗？',
        confirmClearCompleted: '您确定要清除所有已完成的任务吗？',
        item: {
            taskCompleted: '任务已执行完成',
            error: '错误',
            parameters: '参数',
            enabled: '已启用',
            disabled: '已禁用',
            execute: '执行任务',
            ignore: '忽略',
            editParams: '编辑参数',
            closeParams: '关闭参数',
            agentExecuting: '{agent} Agent正在执行任务...',
            aiExecuting: 'AI 代理正在自动执行任务...',
            paramNames: {
                '收件人': '收件人',
                '主题': '主题',
                '开始时间': '开始时间',
                '结束时间': '结束时间',
                '会议ID': '会议ID',
                '会议密码': '会议密码',
                '会议时长': '会议时长',
                '会议时区': '会议时区',
                '标题': '标题',
                '时间': '时间',
                '参与者': '参与者',
                '参会人': '参会人',
                '内容': '内容',
                '日期': '日期',
                '地点': '地点',
                '描述': '描述',
                '正文': '正文'
            }
        },
        promptDisplay: {
            title: '您的个性化提示模板',
            subtitle: '基于您的信息生成的智能分析模板',
            howToUse: '如何使用此模板：',
            step1: '此模板将在您停止录制时自动应用',
            step2: '系统会基于您的专业背景分析录制内容',
            step3: '生成的洞察将显示在摘要面板中',
            copied: '已复制到剪贴板',
            copy: '复制模板',
            start: '开始使用',
            loading: '正在加载提示模板...'
        },
        recordingIndicator: {
            recording: '录制中'
        }
    },
    app: {
        viewPrompt: '查看提示模板',
        profileSettings: '个人设置',
        settings: '设置',
        devMode: ''
    },
    commandPalette: {
        placeholder: '你想做什么？（例如："给小明发邮件讨论项目"）',
        agentPlaceholder: '问任何问题或运行命令…',
        addContext: '添加上下文',
        contextTitle: '上下文与文件',
        addFiles: '添加文件',
        dragDrop: '拖拽文件到这里，或点击浏览',
        navigate: '导航',
        select: '选择',
        send: '发送',
        toggleContext: '上下文',
        close: '关闭',
        helperTitle: 'AI 智能助手',
        helperDesc: '提问、运行命令，或让 AI 帮助您完成任何任务',
        commands: {
            sendEmail: { title: '发送邮件', desc: '撰写并发送邮件给某人' },
            scheduleEvent: { title: '安排日程', desc: '创建日历事件或会议' },
            createDoc: { title: '创建文档', desc: '在飞书中生成新文档' },
            createTask: { title: '创建任务', desc: '添加新任务到待办列表' },
            searchInfo: { title: '搜索信息', desc: '搜索和检索信息' },
            sendMessage: { title: '发送消息', desc: '通过飞书或Slack发送消息' }
        },
        aiInterpret: { title: '让AI理解', desc: '' },
        shortcut: '⌘K 快速命令',
        taskCreated: '任务已创建',
        tasksCreated: '个任务已创建',
        attachFile: '添加附件',
        contextAvailable: '录制上下文可用',
        contextHint: '提及"上下文"将自动包含录制内容',
        contextHintShort: '说"上下文"以包含录制内容',
        agent: {
            title: 'Hippo 智能助手',
            thinking: '思考中…',
            ready: '就绪',
            stopped: '已停止',
            stop: '停止',
            retry: '重试',
            regenerate: '重新生成',
            copy: '复制',
            inputPlaceholder: '输入您的消息…'
        }
    },
    skills: {
        title: '已学技能',
        alert: '已学习 {count} 项新技能!',
        viewAll: '查看',
        learnedCount: '项技能',
        empty: '暂无技能',
        emptyDesc: '通过屏幕录制学习到的技能将显示在这里。',
        clear: '清除全部',
        clearConfirm: '确定要清除所有已学技能吗？',
        delete: '删除',
        selectHint: '选择技能',
        selectedSkill: '已选技能',
        closeHint: '关闭',
        useHint: '在命令面板中使用 @ 引用技能'
    },
    highlight: {
        start: '标记 SOP',
        stop: '停止标记',
        active: '标记中',
        waiting: '分析中...',
        success: '已学习新技能',
        error: '标记分析失败'
    }
  },
  en: {
    onboarding: {
      welcome: 'Welcome to HippoGenius',
      subtitle: 'Set up your preferences to generate your personalized AI analysis template',
      required: 'This step is required to start',
      step1: 'Step 1 / 2',
      step1Title: 'Personal Settings',
      step2: 'Step 2 / 2',
      step2Title: 'Template Generated',
      contentBg: 'Recording Context',
      infoSource: 'Information Source',
      occupationType: 'Occupation',
      personalFocus: 'Personal Focus',
      remainingChars: 'chars left',
      placeholderFocus: 'Describe your key focus areas...',
      summaryMode: 'Summary Depth',
      select: 'Select...',
      cancel: 'Cancel',
      generating: 'Generating...',
      start: 'Get Started',
      templateGenerated: '✨ Personalized Template Generated',
      templateSubtitle: 'Customized analysis framework based on your profile',
      successMessage: 'Template generated successfully! It will be automatically applied to your recordings for personalized insights.',
      copy: 'Copy Template',
      copied: 'Copied',
      error: 'Failed to generate prompt',
      emptyError: 'Empty prompt received',
      fallbackTemplate: 'Generating template, please wait...',
      switchLang: '切换到中文'
    },
    settings: {
      title: 'Settings',
      subtitle: 'Update your personal information for better experience',
      success: 'Settings updated successfully!',
      update: 'Save Changes',
      updating: 'Updating...',
      // API Settings
      apiSettings: 'API Settings',
      apiEndpoint: 'API Endpoint',
      apiKey: 'API Key',
      modelName: 'Model Name',
      endpointHelp: 'Compatible OpenAI API endpoint',
      modelHelp: 'Model name (e.g. gpt-3.5-turbo, gpt-4)',
      cancel: 'Cancel',
      save: 'Save Settings',
    },
    options: {
      contentBg: {
        '工作': 'Work',
        '社交': 'Social',
        '成长': 'Growth'
      },
      infoSource: {
        '虚拟屏幕录制': 'Screen Recording',
        '线下录音': 'Offline Recording',
        '多模态笔记': 'Multimodal Notes'
      },
      occupationType: {
        '投资人': 'Investor',
        '律师': 'Lawyer',
        '记者': 'Journalist',
        '产品经理': 'Product Manager',
        '医生': 'Doctor'
      },
      summaryMode: {
        '简洁': 'Concise',
        '适中': 'Moderate',
        '详细': 'Detailed'
      }
    },
    chat: {
        howCanIHelp: 'How can I help you?',
        startPrompt: 'Start recording or type a message',
        inputPlaceholder: 'Type your question...',
        thinking: 'Thinking...',
        aiWarning: 'AI may make mistakes. Please verify important information.',
        error: {
            auth: 'Authentication failed. Please check your API key in settings.',
            notFound: 'API endpoint not found. Please check your API configuration.',
            rateLimit: 'Rate limit exceeded. Please try again later.',
            network: 'Network error. Please check your connection and API settings.',
            general: 'Error',
            default: 'Sorry, an error occurred while processing your request.'
        },
        contextIntro: 'You have access to the following context from user screen recording:\n\n{context}\n\nPlease use this context to provide more relevant and specific answers.',
        recording: {
            start: 'Start Recording',
            stop: 'Stop Recording'
        },
        promptSuggestions: {
            select: 'Select a prompt suggestion...',
            loading: 'Generating prompt suggestions'
        },
        contextSelector: {
            title: 'Recording Context',
            selectAll: 'Select All',
            clearAll: 'Clear All'
        },
        message: {
            you: 'You',
            assistant: 'Assistant',
            usingContext: 'Using screen context',
            copy: 'Copy',
            retry: 'Retry'
        },
        quickCommand: {
            hint: 'Press',
            hintSuffix: 'to quickly create tasks'
        }
    },
    summary: {
        title: 'Context Insights',
        loading: 'Analyzing screen content...',
        keyInsights: 'KEY INSIGHTS',
        todoItems: 'TO-DO ITEMS',
        waitingTitle: 'Waiting for Context',
        waitingDesc: 'Start recording your screen to see AI-generated insights and tasks.'
    },
    tasks: {
        title: 'Tasks',
        pending: 'Pending',
        filter: 'Filter tasks...',
        tabs: {
            all: 'All',
            pending: 'Pending',
            completed: 'Done'
        },
        noHistory: 'No History',
        noHistoryDesc: 'Executed tasks will appear here',
        noTasks: 'No tasks found',
        noMatch: 'No matching tasks',
        startRecording: 'Start recording to detect actionable tasks',
        detecting: 'Tasks detected from your screen will appear here',
        addSample: 'Add Sample Task',
        clearHistory: 'Clear History',
        completedCount: 'Completed',
        failedCount: 'Failed',
        noRecords: 'No history',
        clearAll: 'Clear All',
        executing: 'Running',
        executeAll: 'Run All',
        confirmClearAll: 'Are you sure you want to clear all tasks?',
        confirmClearCompleted: 'Are you sure you want to clear all completed tasks?',
        item: {
            taskCompleted: 'Task executed successfully',
            error: 'Error',
            parameters: 'Parameters',
            enabled: 'Enabled',
            disabled: 'Disabled',
            execute: 'Execute Task',
            ignore: 'Ignore',
            editParams: 'Edit Parameters',
            closeParams: 'Close Parameters',
            agentExecuting: '{agent} Agent is executing task...',
            aiExecuting: 'AI Agent is automatically executing task...',
            paramNames: {
                '收件人': 'Recipient',
                '主题': 'Subject',
                '开始时间': 'Start Time',
                '结束时间': 'End Time',
                '会议ID': 'Meeting ID',
                '会议密码': 'Meeting Password',
                '会议时长': 'Duration',
                '会议时区': 'Timezone',
                '标题': 'Title',
                '时间': 'Time',
                '参与者': 'Participants',
                '参会人': 'Participants',
                '内容': 'Content',
                '日期': 'Date',
                '地点': 'Location',
                '描述': 'Description',
                '正文': 'Body'
            }
        },
        promptDisplay: {
            title: 'Your Personalized Prompt Template',
            subtitle: 'Smart analysis template generated based on your info',
            howToUse: 'How to use this template:',
            step1: 'This template will be automatically applied when you stop recording',
            step2: 'System analyzes recording content based on your professional background',
            step3: 'Generated insights will appear in the summary panel',
            copied: 'Copied to clipboard',
            copy: 'Copy Template',
            start: 'Start Using',
            loading: 'Loading prompt template...'
        },
        recordingIndicator: {
            recording: 'Recording'
        }
    },
    app: {
        viewPrompt: 'View Prompt Template',
        profileSettings: 'Profile Settings',
        settings: 'Settings',
        devMode: ''
    },
    commandPalette: {
        placeholder: "What would you like to do? (e.g., 'Send email to John about project')",
        agentPlaceholder: 'Ask anything or run a command…',
        addContext: 'add context',
        contextTitle: 'Context & Files',
        addFiles: 'Add Files',
        dragDrop: 'Drag & drop files here, or click to browse',
        navigate: 'Navigate',
        select: 'Select',
        send: 'Send',
        toggleContext: 'Context',
        close: 'Close',
        helperTitle: 'AI-Powered Assistant',
        helperDesc: 'Ask questions, run commands, or let AI help you with any task',
        commands: {
            sendEmail: { title: 'Send Email', desc: 'Compose and send an email to someone' },
            scheduleEvent: { title: 'Schedule Event', desc: 'Create a calendar event or meeting' },
            createDoc: { title: 'Create Document', desc: 'Generate a new document in Feishu' },
            createTask: { title: 'Create Task', desc: 'Add a new task to your to-do list' },
            searchInfo: { title: 'Search Information', desc: 'Search and retrieve information' },
            sendMessage: { title: 'Send Message', desc: 'Send a message via Feishu or Slack' }
        },
        aiInterpret: { title: 'Let AI interpret', desc: '' },
        shortcut: '⌘K Quick Command',
        taskCreated: 'Task created',
        tasksCreated: 'tasks created',
        attachFile: 'Attach file',
        contextAvailable: 'Recording context available',
        contextHint: 'Mention "context" to include recording',
        contextHintShort: 'Say "context" to include recording',
        agent: {
            title: 'Hippo Agent',
            thinking: 'Thinking…',
            ready: 'Ready',
            stopped: 'Stopped',
            stop: 'Stop',
            retry: 'Retry',
            regenerate: 'Regenerate',
            copy: 'Copy',
            inputPlaceholder: 'Type your message…'
        }
    },
    skills: {
        title: 'Learned Skills',
        alert: 'Learned {count} new skill(s)!',
        viewAll: 'View',
        learnedCount: 'skills learned',
        empty: 'No skills yet',
        emptyDesc: 'Skills learned from screen recordings will appear here.',
        clear: 'Clear All',
        clearConfirm: 'Are you sure you want to clear all learned skills?',
        delete: 'Delete',
        selectHint: 'Select a skill',
        selectedSkill: 'Selected skill',
        closeHint: 'Close',
        useHint: 'Use @ in Command Palette to reference skills'
    },
    highlight: {
        start: 'Highlight SOP',
        stop: 'Stop Highlight',
        active: 'Highlighting',
        waiting: 'Analyzing...',
        success: 'New skill learned',
        error: 'Highlight analysis failed'
    }
  }
};

type TranslationKeys = typeof translations[Language];
export const t = derived(currentLanguage, ($lang): TranslationKeys => translations[$lang]);

export function toggleLanguage() {
  currentLanguage.update(lang => lang === 'zh' ? 'en' : 'zh');
}

// Helper function to translate profile values to the current language for backend
export function translateProfileForBackend(profile: {
  content_bg: string;
  info_source: string;
  occupation_type: string;
  personal_focus: string;
  summary_mode: string;
}, lang: Language): {
  content_bg: string;
  info_source: string;
  occupation_type: string;
  personal_focus: string;
  summary_mode: string;
} {
  const opts = translations[lang].options;
  return {
    content_bg: opts.contentBg[profile.content_bg as keyof typeof opts.contentBg] || profile.content_bg,
    info_source: opts.infoSource[profile.info_source as keyof typeof opts.infoSource] || profile.info_source,
    occupation_type: opts.occupationType[profile.occupation_type as keyof typeof opts.occupationType] || profile.occupation_type,
    personal_focus: profile.personal_focus, // Keep as-is since it's user-entered text
    summary_mode: opts.summaryMode[profile.summary_mode as keyof typeof opts.summaryMode] || profile.summary_mode
  };
}
