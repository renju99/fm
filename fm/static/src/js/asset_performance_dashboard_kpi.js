/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class AssetPerformanceDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            kpis: [],
            charts: [],
            loading: true,
            error: null,
            facilities: [],
            filters: {
                period_type: 'month',
                facility_id: '',
                date_from: '',
                date_to: '',
            }
        });

        onWillStart(async () => {
            await this.loadFacilities();
            await this.loadData();
        });

        onMounted(() => {
            if (!this.state.loading && this.state.charts.length > 0) {
                this.renderAllCharts();
            }
        });
    }

    async loadFacilities() {
        try {
            this.state.facilities = await this.orm.searchRead(
                'facilities.facility',
                [],
                ['id', 'name'],
                { order: 'name' }
            );
        } catch (error) {
            console.error("Error loading facilities:", error);
            this.state.facilities = [];
        }
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            const filters = {
                period_type: this.state.filters.period_type
            };
            
            if (this.state.filters.facility_id) {
                filters.facility_id = parseInt(this.state.filters.facility_id);
            }
            
            if (this.state.filters.date_from) {
                filters.date_from = this.state.filters.date_from;
            }
            
            if (this.state.filters.date_to) {
                filters.date_to = this.state.filters.date_to;
            }
            
            const data = await this.orm.call(
                'facilities.asset.performance.dashboard',
                'get_dashboard_data_api',
                [],
                { filters: filters }
            );
            
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
        } catch (error) {
            console.error("Asset performance dashboard error:", error);
            this.state.error = "Failed to load dashboard data: " + error.message;
        } finally {
            this.state.loading = false;
        }
    }

    renderAllCharts() {
        setTimeout(() => {
            this.state.charts.forEach((chartData, index) => {
                this.renderChart(index, chartData);
            });
        }, 100);
    }

    renderChart(index, chartData) {
        const canvas = document.getElementById(`asset_perf_chart_${index}`);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        
        if (canvas.chart) {
            canvas.chart.destroy();
        }
        
        const self = this;
        
        canvas.chart = new Chart(ctx, {
            type: chartData.type,
            data: {
                labels: chartData.labels,
                datasets: chartData.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false }
                },
                scales: (chartData.type === 'pie' || chartData.type === 'doughnut') ? {} : {
                    y: { beginAtZero: true }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const element = elements[0];
                        const datasetIndex = element.datasetIndex;
                        const dataIndex = element.index;
                        const label = chartData.labels[dataIndex];
                        const value = chartData.datasets[datasetIndex].data[dataIndex];
                        
                        // Trigger drilldown based on chart type and title
                        self.onChartClick(chartData, label, value, dataIndex);
                    }
                }
            }
        });
    }
    
    async onChartClick(chartData, label, value, dataIndex) {
        try {
            // Determine which drilldown action to call based on chart title
            let actionName = null;
            
            if (chartData.title && chartData.title.toLowerCase().includes('cost')) {
                actionName = 'action_drilldown_maintenance_costs';
            } else if (chartData.title && chartData.title.toLowerCase().includes('work order')) {
                actionName = 'action_drilldown_work_orders';
            } else if (chartData.title && chartData.title.toLowerCase().includes('downtime')) {
                actionName = 'action_drilldown_downtime_analysis';
            } else {
                actionName = 'action_drilldown_asset_performance';
            }
            
            const params = [
                this.state.filters.date_from || null,
                this.state.filters.date_to || null,
                this.state.filters.facility_id || null,
                null
            ];
            
            const action = await this.orm.call(
                'facilities.asset.performance',
                actionName,
                params
            );
            
            if (action) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.error("Chart click error:", error);
        }
    }

    async onRefresh() {
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }

    async onPeriodChange(event) {
        this.state.filters.period_type = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }
    
    async onFacilityChange(event) {
        this.state.filters.facility_id = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }
    
    async onDateFromChange(event) {
        this.state.filters.date_from = event.target.value;
        if (this.state.filters.date_to) {
            await this.loadData();
            if (!this.state.loading && this.state.charts.length > 0) {
                this.renderAllCharts();
            }
        }
    }
    
    async onDateToChange(event) {
        this.state.filters.date_to = event.target.value;
        if (this.state.filters.date_from) {
            await this.loadData();
            if (!this.state.loading && this.state.charts.length > 0) {
                this.renderAllCharts();
            }
        }
    }
    
    async onClearFilters() {
        this.state.filters = {
            period_type: 'month',
            facility_id: '',
            date_from: '',
            date_to: '',
        };
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }

    async onKPIClick(kpiType) {
        if (!kpiType) return;
        
        try {
            // Map KPI types to drilldown actions
            const actionMap = {
                'total_assets': 'action_drilldown_assets',
                'total_value': 'action_drilldown_assets',
                'total_workorders': 'action_drilldown_work_orders',
                'completed_workorders': 'action_drilldown_work_orders',
                'pending_workorders': 'action_drilldown_work_orders',
                'overdue_workorders': 'action_drilldown_work_orders',
                'maintenance_cost': 'action_drilldown_maintenance_costs',
                'total_labor_cost': 'action_drilldown_maintenance_costs',
                'downtime_hours': 'action_drilldown_downtime_analysis',
                'avg_roi': 'action_drilldown_asset_performance',
                'utilization_rate': 'action_drilldown_asset_performance',
                'efficiency_score': 'action_drilldown_asset_performance',
                'asset_health_score': 'action_drilldown_asset_performance',
                'maintenance_efficiency': 'action_drilldown_maintenance_efficiency'
            };
            
            const actionName = actionMap[kpiType];
            if (!actionName) {
                console.log("No drilldown action defined for KPI:", kpiType);
                return;
            }
            
            const params = [
                this.state.filters.date_from || null,
                this.state.filters.date_to || null,
                this.state.filters.facility_id ? parseInt(this.state.filters.facility_id) : null,
                null
            ];
            
            const action = await this.orm.call(
                'facilities.asset.performance',
                actionName,
                params
            );
            
            if (action) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.error("KPI click error:", error);
        }
    }
}

AssetPerformanceDashboard.template = "facilities_management.AssetPerformanceDashboardClient";

registry.category("actions").add("facilities_asset_performance_dashboard_kpi", AssetPerformanceDashboard);

