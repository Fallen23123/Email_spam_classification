export default function Checkbox({ className = '', ...props }) {
    return (
        <input
            {...props}
            type="checkbox"
            className={
                'rounded border-white/20 bg-white/5 text-teal-300 shadow-sm focus:ring-2 focus:ring-teal-300/30 focus:ring-offset-0 ' +
                className
            }
        />
    );
}
