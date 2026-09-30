import { ContinuousScale } from "./continuous_scale";
import type * as p from "../../core/properties";
export declare namespace LinearScale {
    type Attrs = p.AttrsOf<Props>;
    type Props = ContinuousScale.Props;
}
export interface LinearScale extends LinearScale.Attrs {
}
export declare class LinearScale extends ContinuousScale {
    properties: LinearScale.Props;
    constructor(attrs?: Partial<LinearScale.Attrs>);
    get s_compute(): (x: number) => number;
    get s_invert(): (sx: number) => number;
    static linear_compute(source_start: number, source_end: number, target_start: number, target_end: number): [number, number];
}
//# sourceMappingURL=linear_scale.d.ts.map