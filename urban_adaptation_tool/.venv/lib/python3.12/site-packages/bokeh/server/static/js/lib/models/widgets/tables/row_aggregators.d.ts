import type { SlickGroupTotals } from "slickgrid";
import type { Aggregator } from "slickgrid";
import type * as p from "../../../core/properties";
import { Model } from "../../../model";
export declare namespace RowAggregator {
    type Attrs = p.AttrsOf<Props>;
    type Props = Model.Props & {
        field_: p.Property<string>;
    };
}
export interface RowAggregator extends RowAggregator.Attrs {
    readonly key: string;
}
export declare abstract class RowAggregator extends Model {
    properties: RowAggregator.Props;
    protected _aggregator: Aggregator;
    protected abstract readonly aggregator_cls: new (field: string) => Aggregator;
    constructor(attrs?: Partial<RowAggregator.Attrs>);
    init(): void;
    accumulate(item: {
        [key: string]: unknown;
    }): void;
    storeResult(totals: SlickGroupTotals): void;
}
export declare class AvgAggregator extends RowAggregator {
    readonly key = "avg";
    protected readonly aggregator_cls: typeof import("slickgrid").AvgAggregator;
}
export declare class MinAggregator extends RowAggregator {
    readonly key = "min";
    protected readonly aggregator_cls: typeof import("slickgrid").MinAggregator;
}
export declare class MaxAggregator extends RowAggregator {
    readonly key = "max";
    protected readonly aggregator_cls: typeof import("slickgrid").MaxAggregator;
}
export declare class SumAggregator extends RowAggregator {
    readonly key = "sum";
    protected readonly aggregator_cls: typeof import("slickgrid").SumAggregator;
}
//# sourceMappingURL=row_aggregators.d.ts.map