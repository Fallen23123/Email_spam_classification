export default function PrimaryButton({
    className = '',
    disabled,
    children,
    ...props
}) {
    return (
        <button
            {...props}
            className={
                `inline-flex items-center justify-center rounded-2xl border border-white/10 bg-gradient-to-r from-teal-300 via-cyan-300 to-amber-300 px-5 py-3 text-xs font-semibold uppercase tracking-[0.24em] text-slate-950 shadow-[0_18px_40px_rgba(94,234,212,0.24)] transition duration-150 ease-in-out hover:-translate-y-0.5 hover:shadow-[0_22px_44px_rgba(94,234,212,0.32)] focus:outline-none focus:ring-2 focus:ring-teal-200 focus:ring-offset-2 focus:ring-offset-slate-950 active:translate-y-0 ${
                    disabled && 'opacity-25'
                } ` + className
            }
            disabled={disabled}
        >
            {children}
        </button>
    );
}
