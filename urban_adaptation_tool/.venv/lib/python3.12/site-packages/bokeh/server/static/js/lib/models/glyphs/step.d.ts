import type { PointGeometry, SpanGeometry } from "../../core/geometry";
import { XYGlyph, XYGlyphView } from "./xy_glyph";
import { Selection } from "../selections/selection";
import * as mixins from "../../core/property_mixins";
import type * as visuals from "../../core/visuals";
import type * as p from "../../core/properties";
import type { Rect } from "../../core/types";
import { StepMode } from "../../core/enums";
import type { Context2d } from "../../core/util/canvas";
type XY = {
    x: number;
    y: number;
};
export interface StepView extends Step.Data {
}
export declare class StepView extends XYGlyphView {
    model: Step;
    visuals: Step.Visuals;
    load_glglyph(): Promise<typeof import("../../all/main").StepGL>;
    protected _bounds(bounds: Rect): Rect;
    protected _paint(ctx: Context2d, indices: number[], data?: Partial<Step.Data>): void;
    protected _build_step_path(indices: number[], data?: Partial<Step.Data>): {
        xs: number[];
        ys: number[];
    };
    protected _paint_consecutive(ctx: Context2d, indices: number[], data?: Partial<Step.Data>): void;
    protected _render_xy(ctx: Context2d, drawing: boolean, x: number, y: number): boolean;
    draw_legend_for_index(ctx: Context2d, bbox: Rect, _index: number): void;
    get_interpolation_hit(i: number, _geometry: PointGeometry | SpanGeometry): [number, number];
    protected _hit_point(geometry: PointGeometry): Selection;
    protected _hit_span(geometry: SpanGeometry): Selection;
    /**
     * Convert a step between two data points into line segments.
     * For "before" mode: vertical then horizontal.
     * For "after" mode: horizontal then vertical.
     * For "center" mode: horizontal to midpoint, vertical, then horizontal.
     */
    protected _get_step_segments(j: number, mode: StepMode): [XY, XY][];
}
export declare namespace Step {
    type Attrs = p.AttrsOf<Props>;
    type Props = XYGlyph.Props & {
        mode: p.Property<StepMode>;
        pad_before: p.Property<number>;
        pad_after: p.Property<number>;
    } & Mixins;
    type Mixins = mixins.LineScalar;
    type Visuals = XYGlyph.Visuals & {
        line: visuals.LineScalar;
    };
    type Data = p.GlyphDataOf<Props>;
}
export interface Step extends Step.Attrs {
}
export declare class Step extends XYGlyph {
    properties: Step.Props;
    __view_type__: StepView;
    constructor(attrs?: Partial<Step.Attrs>);
}
export {};
//# sourceMappingURL=step.d.ts.map