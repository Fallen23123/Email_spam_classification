import AuthenticatedLayout from '@/Layouts/AuthenticatedLayout';
import { Head } from '@inertiajs/react';
import axios from 'axios';
import { useState } from 'react';
import Tesseract from 'tesseract.js';

const modelRows = [
    'Accutecp 0.9727',
    'Peceson 0.5356',
    'Rosal 0.5923',
    'Efscore 0.9221',
    'ROE-AUT. 0.9556',
];

const decisionSourceBadges = {
    model: {
        label: 'Model',
        className: 'border-slate-400/30 bg-slate-400/10 text-slate-100',
    },
    hot_memory: {
        label: 'Hot Memory',
        className: 'border-amber-400/30 bg-amber-400/10 text-amber-100',
    },
    safe_business_rule: {
        label: 'Safe Business Rule',
        className: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
    },
    phishing_domain_rule: {
        label: 'Phishing Domain Rule',
        className: 'border-rose-400/30 bg-rose-400/10 text-rose-100',
    },
};

const buildReadableSummary = (result) => {
    if (!result) return null;

    const riskySignals = [...(result.subjectSignals || []), ...(result.bodySignals || [])].slice(0, 4);
    const safeSignals = [...(result.subjectSafeSignals || []), ...(result.bodySafeSignals || [])].slice(0, 4);
    const metadataSignals = [...(result.metadataSignals || [])].slice(0, 4);

    if (result.decisionSource === 'phishing_domain_rule' && result.ruleLabel) {
        const details = metadataSignals.length > 0 ? ` Сигнали: ${metadataSignals.join(', ')}.` : '';
        return `Лист виглядає як фішинг, оскільки правило "${result.ruleLabel}" знайшло ознаки імперсонації бренду.${details}`;
    }

    if (result.decisionSource === 'safe_business_rule' && result.ruleLabel) {
        const details = safeSignals.length > 0 ? ` Безпечні сигнали: ${safeSignals.join(', ')}.` : '';
        return `Ймовірно безпечний лист, оскільки він збігся з профілем "${result.ruleLabel}".${details}`;
    }

    if (result.isSpam) {
        if (riskySignals.length > 0) {
            return `Лист виглядає підозріло, оскільки модель знайшла spam-сигнали: ${riskySignals.join(', ')}.`;
        }
        return 'Лист виглядає підозріло, оскільки оцінка моделі перевищила spam-поріг.';
    }

    if (safeSignals.length > 0) {
        return `Ймовірно безпечний лист, оскільки модель знайшла ham-сигнали: ${safeSignals.join(', ')}.`;
    }

    return 'Ймовірно безпечний лист, оскільки оцінка моделі залишилась нижче spam-порогу.';
};

const buildRetrainSummary = (retrainStatus) => {
    if (!retrainStatus) return null;

    if (retrainStatus.inProgress) {
        const startedAt = retrainStatus.startedAt ? ` Старт: ${retrainStatus.startedAt}.` : '';
        return {
            title: 'Модель оновлюється у фоні',
            body: `Автоперенавчання зараз виконується, але аналіз продовжує працювати на поточній версії моделі.${startedAt}`,
            className: 'border-sky-400/20 bg-sky-400/10 text-sky-100',
        };
    }

    if (retrainStatus.lastStatus === 'error') {
        const details = retrainStatus.lastError ? ` Деталі: ${retrainStatus.lastError}` : '';
        return {
            title: 'Автоперенавчання завершилось з помилкою',
            body: `Остання спроба оновлення моделі не завершилась успішно.${details}`,
            className: 'border-rose-400/20 bg-rose-400/10 text-rose-100',
        };
    }

    if (retrainStatus.lastStatus === 'success' && retrainStatus.lastFinishedAt) {
        return {
            title: 'Останнє автоперенавчання завершено',
            body: `Модель успішно оновилась у фоні. Завершення: ${retrainStatus.lastFinishedAt}.`,
            className: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100',
        };
    }

    if (retrainStatus.lastStatus === 'scheduled') {
        return {
            title: 'Автоперенавчання заплановано',
            body: 'Python уже прийняв запит на оновлення моделі й запустить його у фоновому режимі.',
            className: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100',
        };
    }

    return null;
};

const technicalMetricDescriptions = {
    model: 'Назва моделі, яка зараз виконує класифікацію листа.',
    decisionSource: 'Звідки взялося рішення: модель, гаряча пам’ять, safe rule або anti-phishing rule.',
    spamScore: 'Ймовірність спаму від 0 до 1. Чим вище значення, тим підозрілішим виглядає лист.',
    threshold: 'Поріг, вище якого лист вважається спамом. Якщо score нижчий за поріг, лист іде в не спам.',
    wordCount: 'Скільки слів система врахувала в поточному тексті листа.',
    cache: 'Чи був результат взятий з оперативного кешу. HIT швидше, MISS означає повний новий аналіз.',
    totalLatency: 'Загальний час відповіді бекенда для цього аналізу.',
    modelInference: 'Час, витрачений саме на прогноз моделі.',
    explainability: 'Час на побудову пояснень: keywords, section signals та metadata signals.',
    hotMemory: 'Час перевірки, чи є цей лист у ваших уже підтверджених feedback-виправленнях.',
    ruleCheck: 'Час перевірки safe-business і anti-phishing правил перед запуском моделі.',
    cacheLookup: 'Час перевірки оперативного кешу до всіх інших етапів.',
    retrainStatus: 'Поточний стан автоперенавчання моделі у фоні.',
};

const renderTechnicalMetricRow = (label, value, description, valueClassName = 'text-white') => (
    <div className="group relative flex justify-between items-center bg-black/20 p-3 rounded-lg border border-white/5">
        <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">{label}</span>
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-white/10 text-[10px] font-semibold text-slate-400 transition-colors group-hover:border-cyan-300/40 group-hover:text-cyan-200">
                i
            </span>
        </div>
        <span className={`text-sm font-medium ${valueClassName}`}>{value}</span>
        <div className="pointer-events-none absolute left-3 right-3 top-full z-20 mt-2 opacity-0 translate-y-1 transition-all duration-150 group-hover:opacity-100 group-hover:translate-y-0">
            <div className="rounded-xl border border-cyan-300/20 bg-[#0b1422] px-3 py-2 text-xs leading-5 text-slate-200 shadow-[0_16px_40px_rgba(0,0,0,0.45)]">
                {description}
            </div>
        </div>
    </div>
);

// ОНОВЛЕНО: приймаємо initialHistory та initialStats з бекенду (з бази даних)
export default function Dashboard({ auth, initialHistory = [], initialStats = { total: 0, spam: 0, safe: 0 } }) {
    const [text, setText] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [isOcrLoading, setIsOcrLoading] = useState(false);
    const [result, setResult] = useState(null);
    
    // ОНОВЛЕНО: Статистика тепер береться з бази при завантаженні
    const [stats, setStats] = useState(initialStats);
    
    // ОНОВЛЕНО: Історія конвертується з формату бази даних і одразу відображається
    const [history, setHistory] = useState(() => {
        return initialHistory.map(item => ({
            time: new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isSpam: item.is_spam,
            score: item.score
        }));
    });
    
    const [feedbackGiven, setFeedbackGiven] = useState(false);
    const [uploadedFileName, setUploadedFileName] = useState('');
    const [retrainStatus, setRetrainStatus] = useState(null);
    
    // Меню закрите за замовчуванням
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setUploadedFileName(file.name);

        if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
            const reader = new FileReader();
            reader.onload = (event) => setText(event.target.result);
            reader.readAsText(file);
            return;
        }

        if (file.type.startsWith('image/')) {
            setIsOcrLoading(true);
            setText('Зачекайте, система розпізнає текст на зображенні...');
            try {
                const {
                    data: { text: scannedText },
                } = await Tesseract.recognize(file, 'ukr+eng', {
                    logger: (message) => console.log(message),
                });
                setText(scannedText.trim());
            } catch (error) {
                console.error('Помилка OCR:', error);
                alert('Не вдалося розпізнати текст із зображення.');
                setText('');
                setUploadedFileName('');
            } finally {
                setIsOcrLoading(false);
            }
            return;
        }

        alert('Будь ласка, завантажте .txt або зображення.');
        setUploadedFileName('');
    };

    const handleAnalyze = async () => {
        if (!text.trim() || isOcrLoading) return;
        setIsAnalyzing(true);
        try {
            const response = await axios.post('/check-spam', { text });
            const score = response.data.spam_score;
            const threshold = response.data.base_threshold || 0.55;
            const isSpam = score >= threshold;

            setResult({
                score,
                isSpam,
                threshold,
                keywords: response.data.keywords || [],
                decisionSource: response.data.decision_source || 'model',
                ruleLabel: response.data.rule_label || null,
                reason: response.data.reason || null,
                matchedSignals: response.data.matched_signals || [],
                subjectSignals: response.data.subject_signals || [],
                bodySignals: response.data.body_signals || [],
                subjectSafeSignals: response.data.subject_safe_signals || [],
                bodySafeSignals: response.data.body_safe_signals || [],
                metadataSignals: response.data.metadata_signals || [],
                cacheHit: Boolean(response.data.cache_hit),
                explainabilityIncluded: Boolean(response.data.explainability_included),
                explainabilityReason: response.data.explainability_reason || null,
                timings: response.data.timings_ms || {},
            });
            setRetrainStatus({
                inProgress: Boolean(response.data.retrain_in_progress),
                startedAt: response.data.retrain_started_at || null,
                lastFinishedAt: response.data.retrain_last_finished_at || null,
                lastStatus: response.data.retrain_last_status || null,
                lastError: response.data.retrain_last_error || null,
            });
            setStats((prev) => ({
                total: prev.total + 1,
                spam: prev.spam + (isSpam ? 1 : 0),
                safe: prev.safe + (isSpam ? 0 : 1),
            }));

            const now = new Date();
            setHistory((prev) =>
                [{ time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), isSpam, score }, ...prev].slice(0, 10),
            );
            setFeedbackGiven(false);
        } catch (error) {
            console.error('Помилка:', error);
            alert("Помилка з'єднання з сервером. Перевір, чи працює Python.");
        } finally {
            setIsAnalyzing(false);
        }
    };

    const handleFeedback = async (isCorrect) => {
        if (!result) return;
        try {
            const response = await axios.post('/save-feedback', {
                text,
                score: result.score,
                isSpam: result.isSpam,
                isCorrect,
            });
            setRetrainStatus({
                inProgress: Boolean(response.data.retrain_in_progress),
                startedAt: response.data.retrain_started_at || null,
                lastFinishedAt: response.data.retrain_last_finished_at || null,
                lastStatus: response.data.retrain_last_status || (response.data.retrain_scheduled ? 'scheduled' : null),
                lastError: response.data.retrain_last_error || null,
            });
            setFeedbackGiven(true);
        } catch (error) {
            console.error("Помилка збереження відгуку:", error);
        }
    };

    const resultPercent = result ? (result.score * 100).toFixed(1) : '1.6';
    const thresholdPercent = result ? (result.threshold * 100).toFixed(2) : '56.00';
    const isSpam = result?.isSpam;
    const progress = result ? result.score * 100 : 36;
    const decisionBadge = decisionSourceBadges[result?.decisionSource || 'model'] || decisionSourceBadges.model;
    const readableSummary = buildReadableSummary(result);
    const retrainSummary = buildRetrainSummary(retrainStatus);
    const hamRatio = stats.total ? (stats.safe / stats.total) * 100 : 50;
    const spamRatio = stats.total ? (stats.spam / stats.total) * 100 : 18;
    const donutPercent = stats.total ? ((stats.safe / stats.total) * 100).toFixed(1) : '28.1';
    const donutStyle = {
        background: `conic-gradient(#7ee695 0 ${hamRatio}%, #4ea6ad ${hamRatio}% ${Math.min(hamRatio + spamRatio, 100)}%, #203247 ${Math.min(hamRatio + spamRatio, 100)}% 100%)`,
    };

    // НАЧИНКА ПАНЕЛІ
    const sidebarContent = (
        <div className="flex h-full w-full flex-col">
            <div className="border-b border-white/10 px-6 py-6 shrink-0 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-300/25 via-cyan-300/18 to-transparent shadow-neon">
                        <svg className="h-5 w-5 text-cyan-200" viewBox="0 0 24 24" fill="none">
                            <path d="M12 3 5 6v5.6c0 4.6 2.9 8.5 7 10.1 4.1-1.6 7-5.5 7-10.1V6l-7-3Z" fill="currentColor" opacity="0.22" />
                            <path d="M12 4.9 6.8 7v4.6c0 3.7 2.2 6.8 5.2 8 3-1.2 5.2-4.3 5.2-8V7L12 4.9Z" stroke="currentColor" strokeWidth="1.4" />
                        </svg>
                    </div>
                    <p className="text-lg font-semibold text-white">Spam Detection AI</p>
                </div>
                {/* ХРЕСТИК ДЛЯ ЗАКРИТТЯ ПАНЕЛІ */}
                <button
                    onClick={() => setIsSidebarOpen(false)}
                    className="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-white/10"
                    aria-label="Закрити меню"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 custom-scrollbar">
                <p className="text-xl font-semibold text-white">Статистика сесії</p>
                <p className="mt-4 text-sm leading-6 text-slate-400">
                    Коротка аналітика знайдених електронних листів з використанням методу машинного навчання.
                </p>

                <div className="mt-5 grid grid-cols-3 gap-4">
                    <div>
                        <p className="text-3xl font-light text-white">{stats.total}</p>
                        <p className="mt-2 text-xs leading-5 text-slate-400">Перевірок</p>
                    </div>
                    <div>
                        <p className="text-3xl font-light text-white">{stats.spam}</p>
                        <p className="mt-2 text-xs leading-5 text-slate-400">Спам</p>
                    </div>
                    <div>
                        <p className="text-3xl font-light text-emerald-300">{stats.safe}</p>
                        <p className="mt-2 text-xs leading-5 text-slate-400">Безпечне</p>
                    </div>
                </div>

                <div className="my-6 border-t border-white/10" />

                <div className="flex flex-col items-center">
                    <div className="relative flex h-40 w-40 items-center justify-center rounded-full" style={donutStyle}>
                        <div className="absolute inset-[20px] rounded-full bg-[#0f1826]" />
                        <div className="relative text-center">
                            <p className="text-2xl font-medium text-white">{donutPercent}%</p>
                            <p className="text-[10px] uppercase tracking-[0.16em] text-slate-400">безпеки</p>
                        </div>
                    </div>
                    <div className="mt-5 flex w-full items-center justify-center gap-6 text-sm">
                        <div className="flex items-center gap-2 text-slate-300"><span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />Ham</div>
                        <div className="flex items-center gap-2 text-slate-300"><span className="h-2.5 w-2.5 rounded-full bg-rose-300" />Spam</div>
                    </div>
                </div>

                <div className="my-6 border-t border-white/10" />

                <p className="mb-4 text-xl font-semibold text-white">Історія перевірок</p>
                <div className="space-y-3 pb-8">
                    {history.length === 0 ? (
                        <div className="rounded-[1.2rem] bg-white/5 border border-white/10 px-4 py-4 text-sm leading-6 text-slate-400">
                            Історія ще порожня. Після першого аналізу тут з’являться результати.
                        </div>
                    ) : (
                        history.map((item, idx) => (
                            <div key={`${item.time}-${idx}`} className="rounded-[1.2rem] bg-white/5 border border-white/10 px-4 py-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <p className="text-sm text-slate-300">Сьогодні о {item.time}</p>
                                        <p className={`mt-2 text-base font-medium ${item.isSpam ? 'text-rose-300' : 'text-cyan-300'}`}>
                                            {item.isSpam ? 'Спам' : 'Безпечне'} {(item.score * 100).toFixed(1)}%
                                        </p>
                                    </div>
                                    <span className={`rounded-lg px-2 py-1 text-xs ${item.isSpam ? 'bg-rose-400/20 text-rose-100' : 'bg-emerald-400/20 text-emerald-100'}`}>
                                        {item.isSpam ? 'Spam' : 'Safe'}
                                    </span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );

    return (
        <>
            <Head title="Dashboard" />

            <AuthenticatedLayout>
                
                {/* Затемнення фону (лише для мобільних) */}
                {isSidebarOpen && (
                    <div
                        onClick={() => setIsSidebarOpen(false)}
                        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
                    />
                )}

                {/* ГОЛОВНИЙ КОНТЕЙНЕР */}
                <div className="mx-auto max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8 flex items-start">
                    
                    {/* 1. ДЕСКТОПНИЙ САЙДБАР (Керується фізичною шириною і зсувом) */}
                    <div 
                        className="hidden md:block shrink-0 transition-all duration-300 ease-in-out z-10"
                        style={{
                            width: isSidebarOpen ? '320px' : '0px',
                            marginRight: isSidebarOpen ? '32px' : '0px', // 32px = mr-8
                            opacity: isSidebarOpen ? 1 : 0,
                            visibility: isSidebarOpen ? 'visible' : 'hidden',
                            overflow: 'hidden'
                        }}
                    >
                        <aside 
                            className="w-[320px] h-[calc(100vh-6rem)] sticky top-8 flex flex-col rounded-[1.7rem] border border-white/10 shadow-[0_32px_70px_rgba(0,0,0,0.5)] transition-transform duration-300 ease-in-out"
                            style={{ 
                                backgroundColor: '#0f1826',
                                transform: isSidebarOpen ? 'translateX(0)' : 'translateX(-100%)' // Від'їжджає повністю
                            }} 
                        >
                            {sidebarContent}
                        </aside>
                    </div>

                    {/* 2. МОБІЛЬНИЙ САЙДБАР (Керується фізичною позицією) */}
                    <aside 
                        className="md:hidden fixed inset-y-0 z-50 w-[280px] h-full flex flex-col border-r border-white/10 shadow-2xl transition-all duration-300 ease-in-out"
                        style={{ 
                            backgroundColor: '#0f1826',
                            left: isSidebarOpen ? '0px' : '-320px', // Виїжджає повністю
                            visibility: isSidebarOpen ? 'visible' : 'hidden'
                        }} 
                    >
                        {sidebarContent}
                    </aside>

                    {/* 3. ОСНОВНА РОБОЧА ЗОНА */}
                    <main className="flex-1 min-w-0 w-full transition-all duration-300 relative z-20">
                        
                        {/* КНОПКА УПРАВЛІННЯ МЕНЮ */}
                        <div className="mb-6 flex items-center relative z-50">
                            <button
                                type="button"
                                onClick={() => setIsSidebarOpen((prev) => !prev)}
                                className="group flex h-11 w-11 cursor-pointer items-center justify-center rounded-xl border border-white/10 bg-[#0f1826] text-slate-300 shadow-sm transition-all hover:bg-white/20 hover:text-white focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
                                aria-label="Toggle Sidebar"
                            >
                                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="3" y1="12" x2="21" y2="12" className="transition-all duration-300" />
                                    <line x1="3" y1="6" x2="21" y2="6" className={`transition-all duration-300 ${!isSidebarOpen ? '' : 'translate-x-2 opacity-50'}`} />
                                    <line x1="3" y1="18" x2="21" y2="18" className={`transition-all duration-300 ${!isSidebarOpen ? '' : '-translate-x-2 opacity-50'}`} />
                                </svg>
                            </button>
                            <span 
                                className="ml-4 text-sm font-medium text-slate-400 cursor-pointer select-none transition-colors hover:text-white" 
                                onClick={() => setIsSidebarOpen((prev) => !prev)}
                            >
                                {isSidebarOpen ? 'Сховати меню' : 'Відкрити меню'}
                            </span>
                        </div>

                        {/* ЦЕНТРАЛЬНІ КАРТКИ */}
                        <div className="space-y-4 rounded-[1.65rem] border border-white/6 bg-[#111b29]/65 p-4 sm:p-5 shadow-xl relative z-10">
                            
                            {/* Блок аналізу */}
                            <section className="dashboard-card overflow-hidden rounded-[1.45rem] px-6 py-6 sm:px-8">
                                <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
                                    <div className="space-y-5">
                                        <div className="flex items-start gap-4">
                                            <div className="mt-1 flex h-12 w-12 items-center justify-center rounded-2xl border border-rose-300/25 bg-rose-300/8 shrink-0">
                                                <svg className="h-8 w-8 text-rose-200" viewBox="0 0 24 24" fill="none">
                                                    <path d="M12 3 5 6v5.6c0 4.6 2.9 8.5 7 10.1 4.1-1.6 7-5.5 7-10.1V6l-7-3Z" fill="currentColor" opacity="0.18" />
                                                    <path d="M12 4.9 6.8 7v4.6c0 3.7 2.2 6.8 5.2 8 3-1.2 5.2-4.3 5.2-8V7L12 4.9Z" stroke="currentColor" strokeWidth="1.5" />
                                                </svg>
                                            </div>
                                            <div>
                                                <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-5xl">
                                                    Інтелектуальна система детекції спаму
                                                </h1>
                                                <p className="mt-3 max-w-3xl text-base leading-7 text-slate-300">
                                                    Автоматичний аналіз електронних листів з використанням методів машинного навчання та NLP.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap gap-3 text-sm text-slate-400">
                                            <span className="rounded-full border border-white/8 bg-white/[0.03] px-3 py-2">📁 Підтримується TXT, PNG, JPG</span>
                                            <span className="rounded-full border border-white/8 bg-white/[0.03] px-3 py-2">Користувач: {auth.user.name}</span>
                                        </div>

                                        <div className="dashboard-input rounded-[1.15rem] p-3 border border-white/5 bg-black/20">
                                            <div className="flex flex-col gap-3 md:flex-row md:items-center">
                                                <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-teal-300/35 bg-teal-300/10 px-4 py-3 text-sm font-semibold text-teal-200 transition hover:bg-teal-300/20 shrink-0">
                                                    Завантажити файл
                                                    <input type="file" className="hidden" accept=".txt,image/*" onChange={handleFileUpload} disabled={isOcrLoading} />
                                                </label>
                                                <div className="min-w-0 flex-1 truncate rounded-xl border border-white/8 bg-black/40 px-4 py-3 text-sm text-slate-400">
                                                    {uploadedFileName || 'Тут з’явиться назва вашого файлу'}
                                                </div>
                                            </div>

                                            <div className="mt-4">
                                                <textarea
                                                    className="w-full min-h-[190px] bg-white border border-slate-300 rounded-xl p-5 !text-black font-medium placeholder-slate-500 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/30 outline-none transition-all resize-none shadow-inner"
                                                    style={{ color: '#000000', opacity: 1 }}
                                                    placeholder="Вставте текст листа для аналізу..."
                                                    value={text}
                                                    onChange={(e) => setText(e.target.value)}
                                                    disabled={isOcrLoading}
                                                />
                                            </div>

                                            <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                                <div className="flex flex-wrap gap-2 text-xs uppercase tracking-[0.14em] text-slate-400 font-medium">
                                                    <span className="rounded-full border border-white/10 bg-transparent px-3 py-2">
                                                        OCR: {isOcrLoading ? 'активний' : 'очікує'}
                                                    </span>
                                                    <span className="rounded-full border border-white/10 bg-transparent px-3 py-2">
                                                        Статус: {isAnalyzing ? 'аналізуємо' : 'готово'}
                                                    </span>
                                                </div>

                                                <button
                                                    type="button"
                                                    onClick={handleAnalyze}
                                                    disabled={isAnalyzing || isOcrLoading || !text.trim()}
                                                    className="inline-flex items-center justify-center rounded-xl border border-cyan-400/30 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 px-8 py-3 text-sm font-bold text-cyan-100 shadow-lg transition-all hover:bg-cyan-400/30 hover:shadow-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                                                >
                                                    {isAnalyzing ? 'Аналізуємо...' : 'Запустити аналіз'}
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Декоративний вектор */}
                                    <div className="relative hidden min-h-[230px] items-center justify-center xl:flex">
                                        <div className="absolute inset-0 rounded-[2rem] bg-[radial-gradient(circle_at_center,rgba(82,219,255,0.15),transparent_60%)]" />
                                        <svg className="relative h-[230px] w-[230px] text-cyan-200 drop-shadow-[0_0_35px_rgba(56,189,248,0.45)]" viewBox="0 0 220 220" fill="none">
                                            <path d="M110 22 52 46v55.5c0 41.7 24.4 76.9 58 91 33.6-14.1 58-49.3 58-91V46l-58-24Z" stroke="currentColor" strokeWidth="3" opacity="0.9" />
                                            <path d="M110 39 67 56.5v42.9c0 31 17.8 57.4 43 68.4 25.2-11 43-37.4 43-68.4V56.5L110 39Z" fill="currentColor" opacity="0.08" />
                                            <rect x="82" y="82" width="56" height="42" rx="8" stroke="currentColor" strokeWidth="2" />
                                            <path d="m90 116 14-16 13 10 13-16 8 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                                            <circle cx="95" cy="91" r="4" fill="currentColor" />
                                        </svg>
                                    </div>
                                </div>
                            </section>

                            {/* Блок результатів */}
                            <section className="dashboard-card rounded-[1.45rem] px-6 py-6 sm:px-8">
                                <div className="flex items-center gap-3">
                                    <span className="rounded-lg bg-white/6 px-2 py-1 text-sm text-slate-200">📊</span>
                                    <h2 className="text-2xl font-semibold text-white">Результати аналізу</h2>
                                </div>

                                <div className="mt-8 grid gap-8 xl:grid-cols-[0.95fr,1.05fr]">
                                    <div>
                                        <p className="text-sm text-slate-400">Ймовірність спаму</p>
                                        <p className="mt-3 text-6xl font-light text-white">{resultPercent}%</p>
                                        <div className="mt-4">
                                            <span
                                                className={`inline-flex rounded-xl border px-4 py-2.5 text-sm font-medium shadow-md ${
                                                    isSpam
                                                        ? 'border-amber-400/40 bg-amber-400/10 text-amber-300'
                                                        : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                                                }`}
                                            >
                                                {result ? (isSpam ? '⚠️ Висока загроза (Спам)' : '✅ Повідомлення безпечне') : 'Очікуємо аналіз...'}
                                            </span>
                                        </div>
                                        {result && (
                                            <div className="mt-4 flex flex-wrap items-center gap-3">
                                                <span className={`inline-flex rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] ${decisionBadge.className}`}>
                                                    {decisionBadge.label}
                                                </span>
                                                {result.ruleLabel && (
                                                    <span className="inline-flex rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1.5 text-xs font-medium text-cyan-100">
                                                        {result.ruleLabel}
                                                    </span>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                        <div>
                                            <p className="text-sm text-slate-300">Рівень підозрілості</p>
                                            <div className="mt-6 h-4 overflow-hidden rounded-full border border-white/20 bg-black/40 shadow-inner">
                                                <div
                                                    className="h-full rounded-full transition-all duration-1000 ease-out"
                                                style={{ 
                                                    width: result ? `${progress}%` : '0%', 
                                                    backgroundColor: result ? `hsl(${120 - (progress * 1.2)}, 80%, 50%)` : 'transparent'
                                                }}
                                            />
                                        </div>

                                            {result?.keywords && result.keywords.length > 0 && (
                                                <div className="mt-6">
                                                    <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                                        Ключові маркери спаму:
                                                    </p>
                                                    <div className="flex flex-wrap gap-2">
                                                        {result.keywords.map((word, idx) => (
                                                            <span
                                                                key={`${word}-${idx}`}
                                                                className="inline-flex items-center rounded-full border border-rose-500/20 bg-rose-500/10 px-3 py-1 text-xs font-medium text-rose-400 shadow-sm"
                                                            >
                                                                <svg className="mr-1.5 h-2 w-2 fill-current" viewBox="0 0 8 8">
                                                                    <circle cx="4" cy="4" r="3" />
                                                                </svg>
                                                                {word}
                                                            </span>
                                                        ))}
                                                    </div>
                                                    <p className="mt-3 text-[11px] italic text-slate-500">
                                                        * Ці слова найбільше вплинули на рішення моделі.
                                                    </p>
                                                </div>
                                            )}

                                            {(result?.decisionSource === 'safe_business_rule' || result?.decisionSource === 'phishing_domain_rule') && (
                                                <div className={`mt-6 rounded-2xl border px-5 py-4 text-sm ${
                                                    result?.decisionSource === 'phishing_domain_rule'
                                                        ? 'border-rose-400/15 bg-rose-400/5 text-rose-50/90'
                                                        : 'border-emerald-400/15 bg-emerald-400/5 text-emerald-50/90'
                                                }`}>
                                                    <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${
                                                        result?.decisionSource === 'phishing_domain_rule'
                                                            ? 'text-rose-200/80'
                                                            : 'text-emerald-200/80'
                                                    }`}>
                                                        {result?.decisionSource === 'phishing_domain_rule'
                                                            ? 'Чому лист визнано фішинговим'
                                                            : 'Чому лист визнано безпечним'}
                                                    </p>
                                                    {result.reason && (
                                                        <p className={`mt-3 leading-6 ${
                                                            result?.decisionSource === 'phishing_domain_rule'
                                                                ? 'text-rose-100/85'
                                                                : 'text-emerald-100/85'
                                                        }`}>{result.reason}</p>
                                                    )}
                                                    {result.matchedSignals?.length > 0 && (
                                                        <div className="mt-4">
                                                            <p className={`text-xs font-semibold uppercase tracking-[0.16em] ${
                                                                result?.decisionSource === 'phishing_domain_rule'
                                                                    ? 'text-rose-200/75'
                                                                    : 'text-emerald-200/75'
                                                            }`}>
                                                                Знайдені сигнали
                                                            </p>
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {result.matchedSignals.map((signal, idx) => (
                                                                    <span
                                                                        key={`${signal}-${idx}`}
                                                                        className={`inline-flex rounded-full border bg-black/20 px-3 py-1 text-xs font-medium ${
                                                                            result?.decisionSource === 'phishing_domain_rule'
                                                                                ? 'border-rose-300/20 text-rose-100'
                                                                                : 'border-emerald-300/20 text-emerald-100'
                                                                        }`}
                                                                    >
                                                                        {signal}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {readableSummary && (
                                                <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-6 text-slate-100/90">
                                                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300/75">
                                                        Короткий підсумок
                                                    </p>
                                                    <p className="mt-3">{readableSummary}</p>
                                                </div>
                                            )}

                                            {result && (
                                                result.subjectSignals?.length > 0 ||
                                                result.bodySignals?.length > 0 ||
                                                result.subjectSafeSignals?.length > 0 ||
                                                result.bodySafeSignals?.length > 0 ||
                                                result.metadataSignals?.length > 0
                                            ) && (
                                                <div className="mt-6 rounded-2xl border border-cyan-400/12 bg-cyan-400/[0.04] px-5 py-4 text-sm text-slate-100/90">
                                                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200/80">
                                                        Explainability By Section
                                                    </p>

                                                    {result.metadataSignals?.length > 0 && (
                                                        <div className="mt-4">
                                                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-200/75">
                                                                URL / Domain / Sender Signals
                                                            </p>
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {result.metadataSignals.map((signal, idx) => (
                                                                    <span
                                                                        key={`meta-${signal}-${idx}`}
                                                                        className="inline-flex rounded-full border border-amber-300/20 bg-black/20 px-3 py-1 text-xs font-medium text-amber-100"
                                                                    >
                                                                        {signal}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {result.subjectSignals?.length > 0 && (
                                                        <div className="mt-4">
                                                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300/75">
                                                                Subject Signals
                                                            </p>
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {result.subjectSignals.map((signal, idx) => (
                                                                    <span
                                                                        key={`subject-${signal}-${idx}`}
                                                                        className="inline-flex rounded-full border border-cyan-300/20 bg-black/20 px-3 py-1 text-xs font-medium text-cyan-100"
                                                                    >
                                                                        {signal}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {result.bodySignals?.length > 0 && (
                                                        <div className="mt-4">
                                                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-300/75">
                                                                Body Signals
                                                            </p>
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {result.bodySignals.map((signal, idx) => (
                                                                    <span
                                                                        key={`body-${signal}-${idx}`}
                                                                        className="inline-flex rounded-full border border-sky-300/20 bg-black/20 px-3 py-1 text-xs font-medium text-sky-100"
                                                                    >
                                                                        {signal}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {result.subjectSafeSignals?.length > 0 && (
                                                        <div className="mt-4">
                                                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200/75">
                                                                Safe Subject Signals
                                                            </p>
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {result.subjectSafeSignals.map((signal, idx) => (
                                                                    <span
                                                                        key={`subject-safe-${signal}-${idx}`}
                                                                        className="inline-flex rounded-full border border-emerald-300/20 bg-black/20 px-3 py-1 text-xs font-medium text-emerald-100"
                                                                    >
                                                                        {signal}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    {result.bodySafeSignals?.length > 0 && (
                                                        <div className="mt-4">
                                                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200/75">
                                                                Safe Body Signals
                                                            </p>
                                                            <div className="mt-3 flex flex-wrap gap-2">
                                                                {result.bodySafeSignals.map((signal, idx) => (
                                                                    <span
                                                                        key={`body-safe-${signal}-${idx}`}
                                                                        className="inline-flex rounded-full border border-emerald-300/20 bg-black/20 px-3 py-1 text-xs font-medium text-emerald-100"
                                                                    >
                                                                        {signal}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            <div
                                                className={`mt-6 rounded-2xl border px-5 py-4 text-sm leading-relaxed ${
                                                    isSpam
                                                        ? 'border-amber-500/20 bg-amber-500/5 text-amber-100/90'
                                                    : 'border-emerald-500/20 bg-emerald-500/5 text-emerald-100/90'
                                            }`}
                                        >
                                            {result ? (
                                                isSpam ? (
                                                    <p>{resultPercent}% (вищий рівень): система класифікувала повідомлення як потенційний спам. Рекомендуємо не переходити за посиланнями.</p>
                                                ) : (
                                                    <p>{resultPercent}% (низький рівень): система класифікувала повідомлення як НЕ СПАМ. Текст виглядає безпечно.</p>
                                                )
                                            ) : (
                                                <p className="text-slate-500 italic">Після аналізу тут з’явиться короткий висновок моделі.</p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </section>

                            {/* Блок навчання та діагностики */}
                            <div className="grid items-start gap-4 lg:grid-cols-2">
                                <section className="dashboard-card rounded-[1.45rem] px-6 py-6 sm:px-8">
                                    <div>
                                        <div className="flex items-center gap-3">
                                            <span className="rounded-lg bg-white/6 px-2 py-1 text-sm text-slate-200">🧠</span>
                                            <h2 className="text-2xl font-semibold text-white">Навчання моделі</h2>
                                        </div>
                                        <p className="mt-3 max-w-md text-sm leading-6 text-slate-300">
                                            Допоможи моделі стати точнішою: підтвердь, чи правильно система класифікувала цей лист.
                                        </p>
                                    </div>

                                    <div className="mt-6 rounded-[1.35rem] border border-white/8 bg-black/20 p-4 sm:p-5">
                                        <div className="flex flex-col gap-3 sm:flex-row">
                                            <button
                                                type="button"
                                                onClick={() => handleFeedback(true)}
                                                disabled={!result || feedbackGiven}
                                                className="flex-1 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-300 transition-all hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                ✅ Так, правильно
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => handleFeedback(false)}
                                                disabled={!result || feedbackGiven}
                                                className="flex-1 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm font-semibold text-amber-300 transition-all hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                                            >
                                                ❌ Ні, помилка
                                            </button>
                                        </div>

                                        {feedbackGiven && (
                                            <p className="mt-4 text-sm text-cyan-300 animate-pulse">
                                                Дякуємо! Відгук успішно записано в базу.
                                            </p>
                                        )}

                                        {retrainSummary && (
                                            <div className={`mt-4 rounded-2xl border px-4 py-4 text-sm leading-6 ${retrainSummary.className}`}>
                                                <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-80">
                                                    {retrainSummary.title}
                                                </p>
                                                <p className="mt-2">{retrainSummary.body}</p>
                                            </div>
                                        )}
                                    </div>
                                </section>

                                <section className="dashboard-card rounded-[1.45rem] px-6 py-6 sm:px-8">
                                    <div className="flex items-center gap-3">
                                        <span className="rounded-lg bg-white/6 px-2 py-1 text-sm text-slate-200">🧪</span>
                                        <h2 className="text-2xl font-semibold text-white">Технічні метрики</h2>
                                    </div>
                                    
                                    <div className="mt-6 space-y-4">
                                        {renderTechnicalMetricRow(
                                            'Модель',
                                            'LinearSVM Calibrated',
                                            technicalMetricDescriptions.model,
                                            'text-cyan-200',
                                        )}
                                        <div className="group relative flex justify-between items-center bg-black/20 p-3 rounded-lg border border-white/5">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm text-slate-400">Джерело рішення</span>
                                                <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-white/10 text-[10px] font-semibold text-slate-400 transition-colors group-hover:border-cyan-300/40 group-hover:text-cyan-200">
                                                    i
                                                </span>
                                            </div>
                                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${decisionBadge.className}`}>
                                                {result ? decisionBadge.label : '—'}
                                            </span>
                                            <div className="pointer-events-none absolute left-3 right-3 top-full z-20 mt-2 opacity-0 translate-y-1 transition-all duration-150 group-hover:opacity-100 group-hover:translate-y-0">
                                                <div className="rounded-xl border border-cyan-300/20 bg-[#0b1422] px-3 py-2 text-xs leading-5 text-slate-200 shadow-[0_16px_40px_rgba(0,0,0,0.45)]">
                                                    {technicalMetricDescriptions.decisionSource}
                                                </div>
                                            </div>
                                        </div>
                                        {renderTechnicalMetricRow(
                                            'Spam Score',
                                            result ? result.score.toFixed(6) : '—',
                                            technicalMetricDescriptions.spamScore,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Поріг (Threshold)',
                                            result ? result.threshold.toFixed(2) : '0.55',
                                            technicalMetricDescriptions.threshold,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Враховано слів',
                                            text.trim() ? text.trim().split(/\s+/).length : 0,
                                            technicalMetricDescriptions.wordCount,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Cache',
                                            result ? (result.cacheHit ? 'HIT' : 'MISS') : '—',
                                            technicalMetricDescriptions.cache,
                                            result?.cacheHit ? 'text-emerald-200' : 'text-slate-300',
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Total Latency',
                                            result?.timings?.total_ms != null ? `${result.timings.total_ms.toFixed(2)} ms` : '—',
                                            technicalMetricDescriptions.totalLatency,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Model Inference',
                                            result?.timings?.model_inference_ms != null ? `${result.timings.model_inference_ms.toFixed(2)} ms` : '—',
                                            technicalMetricDescriptions.modelInference,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Explainability',
                                            result?.timings?.explainability_ms != null ? `${result.timings.explainability_ms.toFixed(2)} ms` : '—',
                                            technicalMetricDescriptions.explainability,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Hot Memory Lookup',
                                            result?.timings?.hot_memory_lookup_ms != null ? `${result.timings.hot_memory_lookup_ms.toFixed(2)} ms` : '—',
                                            technicalMetricDescriptions.hotMemory,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Rule Check',
                                            result?.timings?.rule_check_ms != null ? `${result.timings.rule_check_ms.toFixed(2)} ms` : '—',
                                            technicalMetricDescriptions.ruleCheck,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Cache Lookup',
                                            result?.timings?.cache_lookup_ms != null ? `${result.timings.cache_lookup_ms.toFixed(2)} ms` : '—',
                                            technicalMetricDescriptions.cacheLookup,
                                        )}
                                        {renderTechnicalMetricRow(
                                            'Статус retrain',
                                            retrainStatus?.inProgress
                                                ? 'У процесі'
                                                : retrainStatus?.lastStatus === 'error'
                                                  ? 'Помилка'
                                                  : retrainStatus?.lastStatus === 'success'
                                                    ? 'Завершено'
                                                    : retrainStatus?.lastStatus === 'scheduled'
                                                      ? 'Заплановано'
                                                      : 'Немає',
                                            technicalMetricDescriptions.retrainStatus,
                                            retrainStatus?.inProgress
                                                ? 'text-sky-200'
                                                : retrainStatus?.lastStatus === 'error'
                                                  ? 'text-rose-200'
                                                  : retrainStatus?.lastStatus === 'success'
                                                    ? 'text-emerald-200'
                                                    : 'text-slate-300',
                                        )}
                                    </div>
                                </section>
                            </div>
                        </div>
                    </main>
                </div>
            </AuthenticatedLayout>
        </>
    );
}
