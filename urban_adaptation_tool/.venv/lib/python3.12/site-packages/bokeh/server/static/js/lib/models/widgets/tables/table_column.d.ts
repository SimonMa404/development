import { CellFormatter } from "./cell_formatters";
import { CellEditor } from "./cell_editors";
import type { ColumnType } from "./definitions";
import type * as p from "../../../core/properties";
import { Sort } from "../../../core/enums";
import { Comparison } from "../../../models/comparisons";
import type { HTMLView } from "../../dom/html";
import { HTML } from "../../dom/html";
import type { DOMView } from "../../../core/dom_view";
import type { ChildView } from "../../../core/build_views";
import { View } from "../../../core/view";
import { Model } from "../../../model";
export declare namespace TableColumn {
    type Attrs = p.AttrsOf<Props>;
    type Props = Model.Props & {
        field: p.Property<string>;
        title: p.Property<string | HTML | null>;
        width: p.Property<number>;
        formatter: p.Property<CellFormatter>;
        editor: p.Property<CellEditor>;
        sortable: p.Property<boolean>;
        default_sort: p.Property<Sort>;
        visible: p.Property<boolean>;
        sorter: p.Property<Comparison | null>;
    };
}
export interface TableColumn extends TableColumn.Attrs {
}
export declare class TableColumnView extends View {
    model: TableColumn;
    readonly parent: DOMView;
    title_view?: HTMLView;
    children_views(): ChildView[];
    lazy_initialize(): Promise<void>;
    connect_signals(): void;
    protected _update_title_view(): Promise<void>;
    protected _title_name(): string | HTMLElement;
    toColumn(): ColumnType;
}
export declare class TableColumn extends Model {
    properties: TableColumn.Props;
    __view_type__: TableColumnView;
    constructor(attrs?: Partial<TableColumn.Attrs>);
}
//# sourceMappingURL=table_column.d.ts.map