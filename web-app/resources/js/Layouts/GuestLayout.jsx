import ApplicationLogo from '@/Components/ApplicationLogo';
import { Link } from '@inertiajs/react';

export default function GuestLayout({ children }) {
    return (
        <div className="relative flex min-h-screen items-center overflow-hidden bg-[var(--bg-main)] px-4 py-8 text-slate-100 sm:px-6 lg:px-8">
            <div className="pointer-events-none absolute inset-0 bg-grid-signal opacity-30" />
            <div className="pointer-events-none absolute left-[-10rem] top-[-6rem] h-72 w-72 rounded-full bg-teal-300/14 blur-3xl" />
            <div className="pointer-events-none absolute bottom-[-9rem] right-[-7rem] h-80 w-80 rounded-full bg-amber-300/14 blur-3xl" />

            <div className="relative mx-auto grid w-full max-w-6xl gap-8 lg:grid-cols-[1.1fr,0.9fr]">
                <section className="surface-panel hidden rounded-[2rem] p-8 lg:flex lg:flex-col lg:justify-between">
                    <div className="space-y-6">
                        <Link href="/" className="inline-flex items-center gap-3">
                            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                                <ApplicationLogo className="h-12 w-12 text-teal-300" />
                            </div>
                            <div>
                                <p className="text-sm uppercase tracking-[0.26em] text-teal-200/80">
                                    Mail Shield
                                </p>
                                <p className="text-2xl font-semibold text-white">
                                    Control Center
                                </p>
                            </div>
                        </Link>

                        <span className="eyebrow">AI + OCR + feedback loop</span>

                        <div className="space-y-4">
                            <h1 className="max-w-xl text-5xl font-semibold leading-tight text-white">
                                Безпечний вхід до системи аналізу листів.
                            </h1>
                            <p className="max-w-xl text-lg leading-8 text-slate-300">
                                Платформа допомагає швидко перевіряти email,
                                скріншоти та текстові файли на підозрілі
                                патерни, а ваш фідбек покращує якість моделі.
                            </p>
                        </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-3">
                        <div className="surface-panel-soft rounded-[1.5rem] p-4">
                            <p className="metric-value">OCR</p>
                            <p className="mt-2 text-sm text-slate-300">
                                Розпізнавання тексту зі скріншотів і фото.
                            </p>
                        </div>
                        <div className="surface-panel-soft rounded-[1.5rem] p-4">
                            <p className="metric-value">AI</p>
                            <p className="mt-2 text-sm text-slate-300">
                                Класифікація з порогом ризику в реальному часі.
                            </p>
                        </div>
                        <div className="surface-panel-soft rounded-[1.5rem] p-4">
                            <p className="metric-value">Loop</p>
                            <p className="mt-2 text-sm text-slate-300">
                                Зворотний зв'язок для подальшого навчання моделі.
                            </p>
                        </div>
                    </div>
                </section>

                <section className="surface-panel glow-border w-full rounded-[2rem] px-6 py-8 sm:px-8">
                    <div className="mb-8 flex items-center gap-4 lg:hidden">
                        <Link href="/" className="rounded-2xl border border-white/10 bg-white/5 p-2">
                            <ApplicationLogo className="h-10 w-10 text-teal-300" />
                        </Link>
                        <div>
                            <p className="text-sm uppercase tracking-[0.24em] text-teal-200/80">
                                Mail Shield
                            </p>
                            <p className="text-xl font-semibold text-white">
                                Secure Access
                            </p>
                        </div>
                    </div>

                    {children}
                </section>
            </div>
        </div>
    );
}
