// Inline Lucide-style line icons (stroke 1.75, round caps) for the Executor AI UI.
// Ported from the design system's ui_kits/web/icons.jsx (window.ExecutorIcons).
import React from "react";

export type IconProps = {
  size?: number;
  color?: string;
  style?: React.CSSProperties;
};

type Shape =
  | string
  | { t: "circle"; cx: number; cy: number; r: number }
  | { t: "rect"; x: number; y: number; w: number; h: number; rx?: number }
  | { t: "line"; x1: number; y1: number; x2: number; y2: number };

const I =
  (shapes: Shape[], vb = "0 0 24 24") =>
  ({ size = 20, color = "currentColor", style }: IconProps = {}) =>
    (
      <svg
        width={size}
        height={size}
        viewBox={vb}
        fill="none"
        stroke={color}
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        style={style}
      >
        {shapes.map((d, i) =>
          typeof d === "string" ? (
            <path key={i} d={d} />
          ) : d.t === "circle" ? (
            <circle key={i} cx={d.cx} cy={d.cy} r={d.r} />
          ) : d.t === "rect" ? (
            <rect key={i} x={d.x} y={d.y} width={d.w} height={d.h} rx={d.rx} />
          ) : (
            <line key={i} x1={d.x1} y1={d.y1} x2={d.x2} y2={d.y2} />
          )
        )}
      </svg>
    );

export const ExecutorIcons = {
  Dashboard: I([
    { t: "rect", x: 3, y: 3, w: 7, h: 9, rx: 1 },
    { t: "rect", x: 14, y: 3, w: 7, h: 5, rx: 1 },
    { t: "rect", x: 14, y: 12, w: 7, h: 9, rx: 1 },
    { t: "rect", x: 3, y: 16, w: 7, h: 5, rx: 1 },
  ]),
  Chat: I(["M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"]),
  Upload: I(["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M17 8l-5-5-5 5", "M12 3v12"]),
  FileText: I(["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z", "M14 2v6h6", "M16 13H8", "M16 17H8", "M10 9H8"]),
  Mic: I([{ t: "rect", x: 9, y: 2, w: 6, h: 11, rx: 3 }, "M19 10v1a7 7 0 0 1-14 0v-1", "M12 18v4", "M8 22h8"]),
  Send: I(["M22 2 11 13", "M22 2 15 22l-4-9-9-4z"]),
  Bell: I(["M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9", "M10.3 21a1.94 1.94 0 0 0 3.4 0"]),
  Will: I([
    "M8 21h12a2 2 0 0 0 2-2v-2H10v2a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v3h4",
    "M19 17V5a2 2 0 0 0-2-2H9",
    "M15 8h-4",
    "M15 12h-4",
  ]),
  Bank: I([
    { t: "line", x1: 3, y1: 22, x2: 21, y2: 22 },
    { t: "line", x1: 6, y1: 18, x2: 6, y2: 11 },
    { t: "line", x1: 10, y1: 18, x2: 10, y2: 11 },
    { t: "line", x1: 14, y1: 18, x2: 14, y2: 11 },
    { t: "line", x1: 18, y1: 18, x2: 18, y2: 11 },
    "M12 2 20 7 4 7Z",
  ]),
  Car: I([
    "M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.6-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2",
    { t: "circle", cx: 7, cy: 17, r: 2 },
    { t: "circle", cx: 17, cy: 17, r: 2 },
  ]),
  Home: I(["m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", "M9 22V12h6v10"]),
  CheckCircle: I(["M22 11.08V12a10 10 0 1 1-5.93-9.14", "m9 11 3 3L22 4"]),
  ChevronRight: I(["m9 18 6-6-6-6"]),
  Plus: I(["M12 5v14", "M5 12h14"]),
  Sparkle: I(["M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z"]),
  Pencil: I(["M12 20h9", "M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"]),
  Check: I(["M20 6 9 17l-5-5"]),
  X: I(["M18 6 6 18", "M6 6l12 12"]),
};

export type IconName = keyof typeof ExecutorIcons;
