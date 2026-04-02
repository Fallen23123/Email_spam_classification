import { Link } from '@inertiajs/react';

export default function NavLink({
    active = false,
    className = '',
    children,
    ...props
}) {
    return (
        <Link
            {...props}
            className={
                'inline-flex items-center rounded-full px-4 py-2 text-sm font-medium leading-5 transition duration-150 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/80 ' +
                (active
                    ? 'bg-white/10 text-white shadow-[0_0_0_1px_rgba(255,255,255,0.08)]'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white') +
                ' ' +
                className
            }
        >
            {children}
        </Link>
    );
}
