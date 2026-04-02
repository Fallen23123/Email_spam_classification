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

            <nav className="sticky top-0 z-30 border-b border-white/8 bg-slate-950/55 backdrop-blur-2xl">
                <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                    <div className="flex min-h-[5rem] items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div className="flex shrink-0 items-center">
                                <Link href="/">
                                    <div className="flex items-center gap-3">
                                        <div className="rounded-2xl border border-white/10 bg-white/5 p-2 shadow-[0_12px_30px_rgba(0,0,0,0.2)]">
                                            <ApplicationLogo className="block h-9 w-9 text-teal-300" />
                                        </div>
                                        <div>
                                            <p className="text-sm uppercase tracking-[0.24em] text-teal-200/80">
                                                Mail Shield
                                            </p>
                                            <p className="text-lg font-semibold text-white">
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
                                                className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium leading-4 text-slate-100 transition duration-150 ease-in-out hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/80"
                                            >
                                                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-teal-300 to-amber-200 text-sm font-semibold text-slate-950">
                                                    {user.name.slice(0, 1).toUpperCase()}
                                                </span>
                                                <span className="text-left">
                                                    <span className="block text-xs uppercase tracking-[0.2em] text-slate-400">
                                                        Активна сесія
                                                    </span>
                                                    <span className="block text-sm text-white">
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
                                className="inline-flex items-center justify-center rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-300 transition duration-150 ease-in-out hover:bg-white/10 hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/80"
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
                    <div className="space-y-2 px-4 pb-4 pt-3">
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
