/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class FacilitiesAnalyticsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            kpis: [],
            charts: [],
            tables: [],
            loading: true,
            error: null,
            facilities: [],
            filters: {
                period_type: 'month',
                facility_id: '',
                work_order_type: '',
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
            // Prepare filters for API call
            const filters = {
                period_type: this.state.filters.period_type
            };
            
            if (this.state.filters.facility_id) {
                filters.facility_ids = [[6, 0, [parseInt(this.state.filters.facility_id)]]];
            }
            
            if (this.state.filters.date_from) {
                filters.date_from = this.state.filters.date_from;
            }
            
            if (this.state.filters.date_to) {
                filters.date_to = this.state.filters.date_to;
            }
            
            const data = await this.orm.call(
                'facilities.management.dashboard',
                'get_dashboard_data_api',
                [],
                { filters: filters }
            );
            
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
            this.state.tables = data.tables || [];
        } catch (error) {
            console.error("Dashboard error:", error);
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
        const canvas = document.getElementById(`facilities_chart_${index}`);
        if (!canvas) {
            console.warn(`Canvas facilities_chart_${index} not found`);
            return;
        }

        const ctx = canvas.getContext('2d');
        
        // Destroy existing chart if it exists
        if (canvas.chart) {
            canvas.chart.destroy();
        }
        
        const chartConfig = {
            type: chartData.type,
            data: {
                labels: chartData.labels,
                datasets: chartData.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            afterLabel: function(context) {
                                if (chartData.drilldown) {
                                    return 'Click to view details';
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: (chartData.type === 'pie' || chartData.type === 'doughnut') ? {} : {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        };
        
        // Add click handler for drill-down if available
        if (chartData.drilldown) {
            chartConfig.options.onClick = async (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const label = chartData.labels[index];
                    await this.onChartClick(chartData.drilldown, label, index);
                }
            };
            
            // Make cursor pointer on hover
            chartConfig.options.onHover = (event, activeElements) => {
                event.native.target.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
            };
        }
        
        canvas.chart = new Chart(ctx, chartConfig);
    }
    
    async onChartClick(drilldownAction, label, index) {
        try {
            const dashboardId = await this.orm.call(
                'facilities.management.dashboard',
                'search',
                [[]],
                { limit: 1 }
            );
            
            if (dashboardId && dashboardId.length > 0) {
                const action = await this.orm.call(
                    'facilities.management.dashboard',
                    drilldownAction,
                    [dashboardId],
                    {
                        label: label,
                        index: index
                    }
                );
                
                if (action) {
                    this.action.doAction(action);
                }
            }
        } catch (error) {
            console.error("Chart drill-down error:", error);
        }
    }

    async onKPIClick(actionName) {
        if (!actionName) return;
        
        try {
            const dashboardId = await this.orm.call(
                'facilities.management.dashboard',
                'search',
                [[]],
                { limit: 1 }
            );
            
            if (dashboardId && dashboardId.length > 0) {
                const action = await this.orm.call(
                    'facilities.management.dashboard',
                    actionName,
                    [dashboardId]
                );
                
                if (action) {
                    this.action.doAction(action);
                }
            }
        } catch (error) {
            console.error("Action error:", error);
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
    
    async onWorkOrderTypeChange(event) {
        this.state.filters.work_order_type = event.target.value;
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
            work_order_type: '',
            date_from: '',
            date_to: '',
        };
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }

    getVariance(current, previous) {
        if (!previous || previous === 0) return 0;
        const numCurrent = typeof current === 'string' ? parseFloat(current.replace(/[^0-9.-]/g, '')) : current;
        const numPrevious = typeof previous === 'string' ? parseFloat(previous.replace(/[^0-9.-]/g, '')) : previous;
        if (isNaN(numCurrent) || isNaN(numPrevious) || numPrevious === 0) return 0;
        return ((numCurrent - numPrevious) / numPrevious * 100).toFixed(1);
    }

    getVarianceClass(current, previous) {
        const variance = parseFloat(this.getVariance(current, previous));
        if (variance === 0) return 'text-muted';
        return variance >= 0 ? 'text-success' : 'text-danger';
    }

    getVarianceIcon(current, previous) {
        const variance = parseFloat(this.getVariance(current, previous));
        if (variance === 0) return 'fa-minus';
        return variance >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
    }
}

FacilitiesAnalyticsDashboard.template = "facilities_management.AnalyticsDashboardClient";

registry.category("actions").add("facilities_analytics_dashboard", FacilitiesAnalyticsDashboard);

