import { Link } from '@inertiajs/react';

export default function ResponsiveNavLink({
    active = false,
    className = '',
    children,
    ...props
}) {
    return (
        <Link
            {...props}
            className={`flex w-full items-center rounded-2xl px-4 py-3 ${
                active
                    ? 'bg-white/10 text-white'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
            } text-base font-medium transition duration-150 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/80 ${className}`}
        >
            {children}
        </Link>
    );
}
