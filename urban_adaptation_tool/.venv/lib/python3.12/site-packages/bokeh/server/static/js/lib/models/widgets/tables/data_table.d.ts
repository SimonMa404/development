import { SlickGrid } from "slickgrid";
import type { SlickDataView, ItemMetadata, ColumnSort } from "slickgrid";
import type * as p from "../../../core/properties";
import type { StyleSheetLike } from "../../../core/dom";
import type { Arrayable } from "../../../core/types";
import type { DOMBoxSizing } from "../../layouts/layout_dom";
import { WidgetView } from "../widget";
import type { ColumnType, Item } from "./definitions";
import { TableWidget } from "./table_widget";
import { TableColumn } from "./table_column";
import type { ColumnarDataSource } from "../../sources/columnar_data_source";
import type { CDSView, CDSViewView } from "../../sources/cds_view";
import type { ChildView, ViewStorage } from "../../../core/build_views";
export declare const AutosizeModes: {
    fit_columns: "FCV";
    fit_viewport: "FVC";
    force_fit: "LFF";
    ignore_viewport: "IGV";
    none: "NOA";
};
export type AutosizeMode = "FCV" | "FVC" | "LFF" | "IGV" | "NOA";
export declare class TableDataProvider implements Partial<SlickDataView<Item>> {
    index: number[];
    source: ColumnarDataSource;
    view: CDSView;
    constructor(source: ColumnarDataSource, view: CDSView);
    init(source: ColumnarDataSource, view: CDSView): void;
    getLength(): number;
    getItem<T extends Item>(offset: number): T;
    getCellValue(i: number, field: string): unknown;
    getItemMetadata(_index: number): ItemMetadata | null;
    getField(offset: number, field: string): unknown;
    setField(offset: number, field: string, value: unknown): void;
    getRecords(): Item[];
    getItems(): Item[];
    slice(start: number, end: number | null, step?: number): Item[];
    sort_data(columns: ColumnSort[]): void;
}
export declare class DataTableView extends WidgetView {
    model: DataTable;
    protected cds_view: CDSViewView;
    protected _column_views: ViewStorage<TableColumn>;
    protected data: TableDataProvider;
    protected grid: SlickGrid<Item>;
    protected _in_selection_update: boolean;
    protected _width: number | null;
    private _needs_full_row_flush;
    get data_source(): p.Property<ColumnarDataSource>;
    protected wrapper_el: HTMLElement;
    children_views(): ChildView[];
    lazy_initialize(): Promise<void>;
    remove(): void;
    connect_signals(): void;
    stylesheets(): StyleSheetLike[];
    _after_resize(): void;
    _after_layout(): void;
    box_sizing(): DOMBoxSizing;
    updateLayout(initialized: boolean, rerender: boolean): void;
    updateGrid(): void;
    updateSelection(): void;
    newIndexColumn(): ColumnType;
    get autosize(): AutosizeMode;
    render(): void;
    protected _render_table(): void;
    _after_render(): void;
    private _is_grid_initialized;
    private _calculate_width;
    _hide_header(): void;
    get_selected_rows(): number[];
}
export declare namespace DataTable {
    type Attrs = p.AttrsOf<Props>;
    type Props = TableWidget.Props & {
        autosize_mode: p.Property<"fit_columns" | "fit_viewport" | "none" | "force_fit" | "ignore_viewport">;
        auto_edit: p.Property<boolean>;
        columns: p.Property<TableColumn[]>;
        fit_columns: p.Property<boolean | null>;
        frozen_columns: p.Property<number | null>;
        frozen_rows: p.Property<number | null>;
        sortable: p.Property<boolean>;
        reorderable: p.Property<boolean>;
        editable: p.Property<boolean>;
        selectable: p.Property<boolean | "checkbox">;
        index_position: p.Property<number | null>;
        index_header: p.Property<string>;
        index_width: p.Property<number>;
        scroll_to_selection: p.Property<boolean>;
        header_row: p.Property<boolean>;
        row_height: p.Property<number>;
        multi_selectable: p.Property<boolean>;
    };
}
export interface DataTable extends DataTable.Attrs {
}
export declare class DataTable extends TableWidget {
    properties: DataTable.Props;
    __view_type__: DataTableView;
    private _sort_columns;
    get sort_columns(): ColumnSort[];
    constructor(attrs?: Partial<DataTable.Attrs>);
    update_sort_columns(sort_cols: ColumnSort[]): void;
    get_scroll_index(grid_range: {
        top: number;
        bottom: number;
    }, selected_indices: Arrayable<number>): number | null;
}
//# sourceMappingURL=data_table.d.ts.map