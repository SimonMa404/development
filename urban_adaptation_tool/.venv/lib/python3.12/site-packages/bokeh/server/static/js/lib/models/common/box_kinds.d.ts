import { Node } from "../coordinates/node";
export declare const Corner: import("../../core/kinds").Kinds.Enum<"bottom_left" | "bottom_right" | "top_left" | "top_right">;
export type Corner = typeof Corner["__type__"];
export declare const Edge: import("../../core/kinds").Kinds.Enum<"bottom" | "left" | "right" | "top">;
export type Edge = typeof Edge["__type__"];
export declare const HitTarget: import("../../core/kinds").Kinds.Enum<"area" | "bottom" | "bottom_left" | "bottom_right" | "left" | "right" | "top" | "top_left" | "top_right">;
export type HitTarget = typeof HitTarget["__type__"];
export declare const Resizable: import("../../core/kinds").Kinds.Enum<"all" | "bottom" | "left" | "none" | "right" | "top" | "x" | "y">;
export type Resizable = typeof Resizable["__type__"];
export declare const Movable: import("../../core/kinds").Kinds.Enum<"both" | "none" | "x" | "y">;
export type Movable = typeof Movable["__type__"];
export declare const Limit: import("../../core/kinds").Kinds.Nullable<number | Node>;
export type Limit = typeof Limit["__type__"];
//# sourceMappingURL=box_kinds.d.ts.map