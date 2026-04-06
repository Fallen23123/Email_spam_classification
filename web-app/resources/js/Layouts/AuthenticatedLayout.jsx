import ApplicationLogo from '@/Components/ApplicationLogo';
import Dropdown from '@/Components/Dropdown';
import NavLink from '@/Components/NavLink';
import ResponsiveNavLink from '@/Components/ResponsiveNavLink';
import { Link, usePage } from '@inertiajs/react';
import { useState } from 'react';

export default function AuthenticatedLayout({ header, children }) {
    const user = usePage().props.auth.user;
    const [showingNavigationDropdown, setShowingNavigationDropdown] =
        useState(false);

    return (
        <div className="relative min-h-screen overflow-hidden bg-[var(--bg-main)] text-slate-100">
            <div className="pointer-events-none absolute inset-0 bg-grid-signal opacity-30" />
            <div className="pointer-events-none absolute left-[-12rem] top-[-10rem] h-80 w-80 rounded-full bg-teal-300/12 blur-3xl" />
            <div className="pointer-events-none absolute bottom-[-8rem] right-[-8rem] h-72 w-72 rounded-full bg-amber-300/12 blur-3xl" />

            <nav className="sticky top-0 z-30 px-3 py-3 sm:px-4 sm:py-4">
                <div className="mx-auto max-w-7xl">
                    <div className="relative rounded-[2.4rem] border border-white/10 bg-slate-950/72 shadow-[0_24px_70px_rgba(2,8,23,0.48)] backdrop-blur-2xl">
                        <div className="pointer-events-none absolute inset-0 rounded-[inherit] bg-[radial-gradient(circle_at_top_left,rgba(94,234,212,0.12),transparent_34%),radial-gradient(circle_at_top_right,rgba(251,191,36,0.10),transparent_26%)]" />
                        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-200/30 to-transparent" />
                        <div className="relative flex min-h-[5.7rem] items-center justify-between gap-4 px-5 sm:px-6 lg:px-8">
                        <div className="flex items-center gap-4">
                            <div className="flex shrink-0 items-center">
                                <Link href="/">
                                    <div className="group flex items-center gap-4">
                                        <div className="relative rounded-[1.5rem] border border-cyan-200/14 bg-white/[0.06] p-2.5 shadow-[0_12px_34px_rgba(0,0,0,0.28)] transition-transform duration-200 group-hover:scale-[1.02]">
                                            <div className="absolute inset-0 rounded-[1.5rem] bg-gradient-to-br from-cyan-300/10 via-transparent to-amber-200/10" />
                                            <ApplicationLogo className="relative block h-9 w-9 text-teal-300" />
                                        </div>
                                        <div className="space-y-1">
                                            <div className="flex items-center gap-2">
                                                <p className="text-[0.78rem] uppercase tracking-[0.28em] text-cyan-200/80">
                                                    Mail Shield
                                                </p>
                                                <span className="hidden rounded-full border border-cyan-300/15 bg-cyan-300/8 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-100/85 sm:inline-flex">
                                                    AI Guard
                                                </span>
                                            </div>
                                            <p className="text-xl font-semibold leading-none text-white">
                                                Spam Intelligence
                                            </p>
                                        </div>
                                    </div>
                                </Link>
                            </div>

                            <div className="hidden items-center gap-3 sm:flex">
                                <NavLink
                                    href={route('dashboard')}
                                    active={route().current('dashboard')}
                                >
                                    Dashboard
                                </NavLink>
                            </div>
                        </div>

                        <div className="hidden sm:flex sm:items-center">
                            <div className="relative">
                                <Dropdown>
                                    <Dropdown.Trigger>
                                        <span className="inline-flex rounded-full">
                                            <button
                                                type="button"
                                                className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.06] px-3 py-2.5 text-sm font-medium leading-4 text-slate-100 shadow-[0_10px_30px_rgba(0,0,0,0.18)] transition duration-150 ease-in-out hover:border-cyan-200/20 hover:bg-white/[0.09] focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/80"
                                            >
                                                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-teal-300 via-cyan-200 to-amber-200 text-sm font-semibold text-slate-950 shadow-[0_8px_22px_rgba(45,212,191,0.28)]">
                                                    {user.name.slice(0, 1).toUpperCase()}
                                                </span>
                                                <span className="text-left leading-tight">
                                                    <span className="block text-[11px] uppercase tracking-[0.24em] text-slate-400">
                                                        Активна сесія
                                                    </span>
                                                    <span className="mt-0.5 block text-sm font-semibold text-white">
                                                        {user.name}
                                                    </span>
                                                </span>
                                                <svg
                                                    className="h-4 w-4 text-slate-400"
                                                    xmlns="http://www.w3.org/2000/svg"
                                                    viewBox="0 0 20 20"
                                                    fill="currentColor"
                                                >
                                                    <path
                                                        fillRule="evenodd"
                                                        d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                                                        clipRule="evenodd"
                                                    />
                                                </svg>
                                            </button>
                                        </span>
                                    </Dropdown.Trigger>

                                    <Dropdown.Content contentClasses="surface-panel p-2 text-slate-100">
                                        <Dropdown.Link
                                            href={route('profile.edit')}
                                        >
                                            Профіль
                                        </Dropdown.Link>
                                        <Dropdown.Link
                                            href={route('logout')}
                                            method="post"
                                            as="button"
                                        >
                                            Вийти
                                        </Dropdown.Link>
                                    </Dropdown.Content>
                                </Dropdown>
                            </div>
                        </div>

                        <div className="-me-2 flex items-center sm:hidden">
                            <button
                                onClick={() =>
                                    setShowingNavigationDropdown(
                                        (previousState) => !previousState,
                                    )
                                }
                                className="inline-flex items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06] p-2.5 text-slate-300 shadow-[0_10px_24px_rgba(0,0,0,0.18)] transition duration-150 ease-in-out hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/80"
                            >
                                <svg
                                    className="h-6 w-6"
                                    stroke="currentColor"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        className={
                                            !showingNavigationDropdown
                                                ? 'inline-flex'
                                                : 'hidden'
                                        }
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth="2"
                                        d="M4 6h16M4 12h16M4 18h16"
                                    />
                                    <path
                                        className={
                                            showingNavigationDropdown
                                                ? 'inline-flex'
                                                : 'hidden'
                                        }
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth="2"
                                        d="M6 18L18 6M6 6l12 12"
                                    />
                                </svg>
                            </button>
                        </div>
                    </div>
                    </div>

                    <div
                        className={
                            (showingNavigationDropdown ? 'block' : 'hidden') +
                            ' sm:hidden'
                        }
                    >
                    <div className="mt-3 overflow-hidden rounded-[1.6rem] border border-white/10 bg-slate-950/80 shadow-[0_20px_48px_rgba(2,8,23,0.42)] backdrop-blur-2xl">
                    <div className="space-y-2 px-4 pb-4 pt-4">
                        <ResponsiveNavLink
                            href={route('dashboard')}
                            active={route().current('dashboard')}
                        >
                            Dashboard
                        </ResponsiveNavLink>
                    </div>

                    <div className="border-t border-white/10 px-4 pb-4 pt-4">
                        <div className="px-4">
                            <div className="text-base font-medium text-white">
                                {user.name}
                            </div>
                            <div className="text-sm font-medium text-slate-400">
                                {user.email}
                            </div>
                        </div>

                        <div className="mt-3 space-y-2">
                            <ResponsiveNavLink href={route('profile.edit')}>
                                Профіль
                            </ResponsiveNavLink>
                            <ResponsiveNavLink
                                method="post"
                                href={route('logout')}
                                as="button"
                            >
                                Вийти
                            </ResponsiveNavLink>
                        </div>
                    </div>
                    </div>
                    </div>
                </div>
            </nav>

            {header && (
                <header className="relative z-10">
                    <div className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
                        <div className="surface-panel rounded-[2rem] px-6 py-6 sm:px-8">
                            {header}
                        </div>
                    </div>
                </header>
            )}

            <main className="relative z-10">{children}</main>
        </div>
    );
}
