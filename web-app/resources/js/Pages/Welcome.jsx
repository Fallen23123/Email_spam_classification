import { Head, Link } from '@inertiajs/react';

const features = [
    {
        title: 'Розпізнавання зображень',
        description:
            'Завантажуйте скріншоти листів або підозрілі банери, а OCR перетворить їх у текст для аналізу.',
        accent: 'from-teal-300/20 to-cyan-300/5',
    },
    {
        title: 'Оцінка ризику',
        description:
            'Модель повертає spam score, щоб ви бачили не лише вердикт, а й рівень впевненості системи.',
        accent: 'from-amber-300/20 to-orange-300/5',
    },
    {
        title: 'Навчання через фідбек',
        description:
            'Коли ви підтверджуєте або спростовуєте результат, система накопичує корисні сигнали для покращення.',
        accent: 'from-rose-300/18 to-red-300/5',
    },
];

const workflow = [
    'Вставте текст листа або завантажте файл.',
    'Система розпізнає контент і перевіряє його на spam-ознаки.',
    'Перегляньте score, історію сесії та підтвердьте точність результату.',
];

export default function Welcome({
    auth,
    canLogin,
    canRegister,
    laravelVersion,
    phpVersion,
}) {
    const stats = [
        { label: 'Формати', value: '.txt + image/*' },
        { label: 'Режим', value: 'AI + OCR' },
        { label: 'Feedback', value: 'SQLite loop' },
    ];

    return (
        <>
            <Head title="Mail Shield" />

            <div className="relative min-h-screen overflow-hidden bg-[var(--bg-main)] text-slate-100">
                <div className="pointer-events-none absolute inset-0 bg-grid-signal opacity-30" />
                <div className="pointer-events-none absolute left-[-12rem] top-[-10rem] h-80 w-80 rounded-full bg-teal-300/16 blur-3xl" />
                <div className="pointer-events-none absolute right-[-10rem] top-[20%] h-72 w-72 rounded-full bg-amber-300/16 blur-3xl" />
                <div className="pointer-events-none absolute bottom-[-12rem] left-[20%] h-80 w-80 rounded-full bg-cyan-300/10 blur-3xl" />

                <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col px-6 py-8 lg:px-10">
                    <header className="flex flex-col gap-6 rounded-[2rem] border border-white/10 bg-slate-950/45 px-6 py-5 backdrop-blur-2xl sm:flex-row sm:items-center sm:justify-between">
                        <Link href="/" className="flex items-center gap-4">
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                                <svg
                                    className="h-10 w-10 text-teal-300"
                                    viewBox="0 0 128 128"
                                    fill="none"
                                    xmlns="http://www.w3.org/2000/svg"
                                >
                                    <path
                                        d="M64 8 20 24v33c0 28.6 18.7 52.6 44 63 25.3-10.4 44-34.4 44-63V24L64 8Z"
                                        fill="currentColor"
                                        opacity="0.2"
                                    />
                                    <path
                                        d="M64 14.5 26 28.2v28.3c0 24.5 15.5 45.6 38 55.1 22.5-9.5 38-30.6 38-55.1V28.2L64 14.5Z"
                                        fill="currentColor"
                                    />
                                    <path
                                        d="M40 46.5a6.5 6.5 0 0 1 6.5-6.5h35a6.5 6.5 0 0 1 6.5 6.5v2.7L64 66.5 40 49.2v-2.7Z"
                                        fill="#04111D"
                                    />
                                    <path
                                        d="M40 52.6 63 68.9a1.8 1.8 0 0 0 2 0L88 52.6v28.9A6.5 6.5 0 0 1 81.5 88h-35A6.5 6.5 0 0 1 40 81.5V52.6Z"
                                        fill="#04111D"
                                    />
                                </svg>
                            </div>
                            <div>
                                <p className="text-sm uppercase tracking-[0.28em] text-teal-200/80">
                                    Mail Shield
                                </p>
                                <p className="text-xl font-semibold text-white">
                                    Spam Intelligence Platform
                                </p>
                            </div>
                        </Link>

                        <nav className="flex flex-wrap items-center gap-3">
                            {auth.user ? (
                                <Link
                                    href={route('dashboard')}
                                    className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10 hover:text-white"
                                >
                                    Відкрити dashboard
                                </Link>
                            ) : (
                                <>
                                    {canLogin && (
                                        <Link
                                            href={route('login')}
                                            className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10 hover:text-white"
                                        >
                                            Увійти
                                        </Link>
                                    )}
                                    {canRegister && (
                                        <Link
                                            href={route('register')}
                                            className="inline-flex items-center rounded-full bg-gradient-to-r from-teal-300 via-cyan-300 to-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:-translate-y-0.5"
                                        >
                                            Створити акаунт
                                        </Link>
                                    )}
                                </>
                            )}
                        </nav>
                    </header>

                    <main className="flex-1 py-10">
                        <section className="grid items-center gap-8 lg:grid-cols-[1.1fr,0.9fr]">
                            <div className="space-y-8">
                                <span className="eyebrow">
                                    Email spam classification
                                </span>

                                <div className="space-y-5">
                                    <h1 className="max-w-3xl text-5xl font-semibold leading-[1.05] text-white sm:text-6xl xl:text-7xl">
                                        Виявляйте підозрілі листи швидше, ніж
                                        вони встигають нашкодити.
                                    </h1>
                                    <p className="max-w-2xl text-lg leading-8 text-slate-300 sm:text-xl">
                                        Платформа поєднує OCR, машинне
                                        навчання та зворотний зв'язок від
                                        користувача, щоб перетворити сирий email
                                        на зрозумілий сигнал ризику.
                                    </p>
                                </div>

                                <div className="flex flex-wrap gap-4">
                                    <Link
                                        href={
                                            auth.user
                                                ? route('dashboard')
                                                : route('login')
                                        }
                                        className="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-teal-300 via-cyan-300 to-amber-300 px-6 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-950 transition hover:-translate-y-0.5"
                                    >
                                        {auth.user
                                            ? 'Перейти до аналізу'
                                            : 'Увійти в систему'}
                                    </Link>

                                    {canRegister && !auth.user && (
                                        <Link
                                            href={route('register')}
                                            className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-6 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-100 transition hover:bg-white/10"
                                        >
                                            Спробувати зараз
                                        </Link>
                                    )}
                                </div>

                                <div className="grid gap-4 sm:grid-cols-3">
                                    {stats.map((stat) => (
                                        <div
                                            key={stat.label}
                                            className="surface-panel-soft rounded-[1.5rem] p-5"
                                        >
                                            <p className="metric-label">
                                                {stat.label}
                                            </p>
                                            <p className="mt-3 text-lg font-semibold text-white">
                                                {stat.value}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="surface-panel glow-border rounded-[2rem] p-6 sm:p-8">
                                <div className="mb-6 flex items-center justify-between">
                                    <div>
                                        <p className="text-sm uppercase tracking-[0.24em] text-slate-400">
                                            Live preview
                                        </p>
                                        <h2 className="mt-2 text-3xl font-semibold text-white">
                                            Сигнали ризику в одному кадрі
                                        </h2>
                                    </div>
                                    <span className="rounded-full border border-rose-400/20 bg-rose-400/12 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-rose-200">
                                        Spam alert
                                    </span>
                                </div>

                                <div className="grid gap-4 sm:grid-cols-2">
                                    <div className="surface-panel-soft rounded-[1.5rem] p-5 sm:col-span-2">
                                        <div className="mb-4 flex items-center justify-between">
                                            <p className="text-sm text-slate-400">
                                                Середній рівень підозрілості
                                            </p>
                                            <p className="text-sm font-semibold text-amber-200">
                                                78.4%
                                            </p>
                                        </div>
                                        <div className="h-3 overflow-hidden rounded-full bg-slate-900/80">
                                            <div className="h-full w-[78.4%] rounded-full bg-gradient-to-r from-amber-300 via-orange-300 to-rose-400 shadow-[0_0_20px_rgba(251,191,36,0.45)]" />
                                        </div>
                                    </div>

                                    <div className="surface-panel-soft rounded-[1.5rem] p-5">
                                        <p className="metric-label">OCR queue</p>
                                        <p className="mt-3 text-4xl font-semibold text-white">
                                            12
                                        </p>
                                        <p className="mt-2 text-sm text-slate-400">
                                            Нові скріншоти готові до аналізу.
                                        </p>
                                    </div>

                                    <div className="surface-panel-soft rounded-[1.5rem] p-5">
                                        <p className="metric-label">Feedback</p>
                                        <p className="mt-3 text-4xl font-semibold text-white">
                                            91%
                                        </p>
                                        <p className="mt-2 text-sm text-slate-400">
                                            Підтверджених прогнозів за сесію.
                                        </p>
                                    </div>
                                </div>

                                <div className="mt-6 space-y-3">
                                    {workflow.map((step, index) => (
                                        <div
                                            key={step}
                                            className="flex items-start gap-4 rounded-[1.5rem] border border-white/8 bg-white/[0.03] px-4 py-4"
                                        >
                                            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-300/12 text-sm font-semibold text-teal-200">
                                                0{index + 1}
                                            </span>
                                            <p className="text-sm leading-7 text-slate-300">
                                                {step}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </section>

                        <section className="mt-10 grid gap-5 lg:grid-cols-3">
                            {features.map((feature) => (
                                <article
                                    key={feature.title}
                                    className="surface-panel rounded-[2rem] p-6"
                                >
                                    <div
                                        className={`mb-6 h-24 rounded-[1.5rem] bg-gradient-to-br ${feature.accent}`}
                                    />
                                    <h3 className="text-2xl font-semibold text-white">
                                        {feature.title}
                                    </h3>
                                    <p className="mt-4 text-base leading-8 text-slate-300">
                                        {feature.description}
                                    </p>
                                </article>
                            ))}
                        </section>
                    </main>

                    <footer className="border-t border-white/8 py-6 text-sm text-slate-400">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <p>Powered by AI & Machine Learning.</p>
                            <p>
                                Laravel v{laravelVersion} • PHP v{phpVersion}
                            </p>
                        </div>
                    </footer>
                </div>
            </div>
        </>
    );
}
