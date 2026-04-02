export default function ApplicationLogo(props) {
    return (
        <svg
            {...props}
            viewBox="0 0 128 128"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
        >
            <path
                d="M64 8 20 24v33c0 28.6 18.7 52.6 44 63 25.3-10.4 44-34.4 44-63V24L64 8Z"
                className="fill-current"
                opacity="0.22"
            />
            <path
                d="M64 14.5 26 28.2v28.3c0 24.5 15.5 45.6 38 55.1 22.5-9.5 38-30.6 38-55.1V28.2L64 14.5Z"
                className="fill-current"
            />
            <path
                d="M40 46.5a6.5 6.5 0 0 1 6.5-6.5h35a6.5 6.5 0 0 1 6.5 6.5v2.7L64 66.5 40 49.2v-2.7Z"
                fill="#04111d"
            />
            <path
                d="M40 52.6 63 68.9a1.8 1.8 0 0 0 2 0L88 52.6v28.9A6.5 6.5 0 0 1 81.5 88h-35A6.5 6.5 0 0 1 40 81.5V52.6Z"
                fill="#04111d"
            />
            <path
                d="m45.5 77.5 15.2-14.2 2.7 1.9a1 1 0 0 0 1.2 0l2.7-1.9 15.2 14.2"
                stroke="#5EEAD4"
                strokeWidth="5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M43.5 43.5 64 58l20.5-14.5"
                stroke="#5EEAD4"
                strokeWidth="5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}
