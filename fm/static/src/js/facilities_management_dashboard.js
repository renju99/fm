/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Domain } from "@web/core/domain";

// ==================== KPI CARD WIDGET ====================

export class KPICardWidget extends Component {
    static template = "facilities_management.KPICardWidget";
    static props = {
        data: Object,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
    }

    get variance() {
        const current = parseFloat(this.props.data.value) || 0;
        const previous = parseFloat(this.props.data.previous_value) || 0;
        if (!previous || previous === 0) return 0;
        return ((current - previous) / previous * 100).toFixed(1);
    }

    get varianceClass() {
        const variance = parseFloat(this.variance);
        if (variance > 0) return 'text-success';
        if (variance < 0) return 'text-danger';
        return 'text-muted';
    }

    get varianceIcon() {
        const variance = parseFloat(this.variance);
        if (variance > 0) return 'fa-arrow-up';
        if (variance < 0) return 'fa-arrow-down';
        return 'fa-minus';
    }

    async onCardClick() {
        if (this.props.data.action) {
            try {
                const action = await this.orm.call(
                    'facilities.management.dashboard',
                    this.props.data.action,
                    [[this.env.searchModel?.resId || 1]]
                );
                this.actionService.doAction(action);
            } catch (error) {
                console.error('Error executing card action:', error);
            }
        }
    }
}

// ==================== CHART WIDGET ====================

export class ChartWidget extends Component {
    static template = "facilities_management.ChartWidget";
    static props = {
        data: Object,
    };

    setup() {
        this.chartRef = useRef("chart");
        this.state = useState({
            chartInstance: null,
        });

        onMounted(() => {
            this.renderChart();
        });
    }

    renderChart() {
        if (!this.chartRef.el) {
            console.error('Chart canvas element not found');
            return;
        }

        const ctx = this.chartRef.el.getContext('2d');
        
        // Destroy existing chart if any
        if (this.state.chartInstance) {
            this.state.chartInstance.destroy();
        }

        // Check if Chart.js is loaded
        if (typeof Chart === 'undefined') {
            console.error('Chart.js is not loaded');
            return;
        }

        try {
            this.state.chartInstance = new Chart(ctx, {
                type: this.props.data.type || 'bar',
                data: {
                    labels: this.props.data.labels || [],
                    datasets: this.props.data.datasets || []
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            display: true,
                        },
                        title: {
                            display: true,
                            text: this.props.data.title || '',
                            font: {
                                size: 16,
                                weight: 'bold'
                            }
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                        }
                    },
                    scales: this.props.data.type === 'pie' || this.props.data.type === 'doughnut' ? {} : {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error rendering chart:', error);
        }
    }

    willUnmount() {
        if (this.state.chartInstance) {
            this.state.chartInstance.destroy();
        }
    }
}

// ==================== TABLE WIDGET ====================

export class TableWidget extends Component {
    static template = "facilities_management.TableWidget";
    static props = {
        data: Object,
    };

    get hasData() {
        return this.props.data.rows && this.props.data.rows.length > 0;
    }
}

// ==================== DASHBOARD CONTROLLER ====================

export class FacilitiesManagementDashboard extends Component {
    static template = "facilities_management.DashboardView";
    static components = { 
        KPICardWidget, 
        ChartWidget,
        TableWidget 
    };
    static props = {
        resId: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        
        this.state = useState({
            data: {
                kpis: [],
                charts: [],
                tables: {},
                metadata: {}
            },
            loading: true,
            error: null,
            selectedPeriod: 'month',
            dashboardId: this.props.resId || null,
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            let dashboard;
            
            // Get or create dashboard record
            if (this.state.dashboardId) {
                dashboard = await this.orm.read(
                    'facilities.management.dashboard',
                    [this.state.dashboardId],
                    ['dashboard_data']
                );
                dashboard = dashboard[0];
            } else {
                // Search for existing dashboard
                const dashboards = await this.orm.searchRead(
                    'facilities.management.dashboard',
                    [],
                    ['id', 'dashboard_data'],
                    { limit: 1 }
                );
                
                if (dashboards.length > 0) {
                    dashboard = dashboards[0];
                    this.state.dashboardId = dashboard.id;
                } else {
                    // Create a new dashboard
                    const newId = await this.orm.create(
                        'facilities.management.dashboard',
                        [{
                            name: 'Main Dashboard',
                            period_type: this.state.selectedPeriod,
                        }]
                    );
                    this.state.dashboardId = newId;
                    
                    dashboard = await this.orm.read(
                        'facilities.management.dashboard',
                        [newId],
                        ['dashboard_data']
                    );
                    dashboard = dashboard[0];
                }
            }
            
            // Parse dashboard data
            if (dashboard.dashboard_data) {
                const parsedData = JSON.parse(dashboard.dashboard_data);
                // Ensure arrays are always defined
                this.state.data = {
                    kpis: parsedData.kpis || [],
                    charts: parsedData.charts || [],
                    tables: parsedData.tables || {},
                    metadata: parsedData.metadata || {}
                };
            }
            
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.error = error.message || 'Failed to load dashboard data';
            // Ensure data structure is always valid even on error
            this.state.data = {
                kpis: [],
                charts: [],
                tables: {},
                metadata: {}
            };
        } finally {
            this.state.loading = false;
        }
    }

    async onPeriodChange(event) {
        const newPeriod = event.target.value;
        this.state.selectedPeriod = newPeriod;
        
        if (this.state.dashboardId) {
            try {
                await this.orm.write(
                    'facilities.management.dashboard',
                    [this.state.dashboardId],
                    { period_type: newPeriod }
                );
                await this.loadDashboardData();
            } catch (error) {
                console.error('Error updating period:', error);
            }
        }
    }

    async onRefresh() {
        if (this.state.dashboardId) {
            try {
                await this.orm.call(
                    'facilities.management.dashboard',
                    'action_refresh_dashboard',
                    [[this.state.dashboardId]]
                );
                await this.loadDashboardData();
            } catch (error) {
                console.error('Error refreshing dashboard:', error);
            }
        }
    }

    async onOpenDashboard() {
        if (this.state.dashboardId) {
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'facilities.management.dashboard',
                res_id: this.state.dashboardId,
                views: [[false, 'form']],
                target: 'current',
            });
        }
    }
}

// ==================== CLIENT ACTION ====================

export class FacilitiesDashboardClientAction extends Component {
    static template = "facilities_management.DashboardClientAction";
    static components = { FacilitiesManagementDashboard };
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        "*": true, // Allow any other props
    };

    setup() {
        this.state = useState({
            resId: 1,
        });
    }
}

// Register as a client action (not a view type)
registry.category("actions").add("facilities_management.dashboard_client_action", FacilitiesDashboardClientAction);

