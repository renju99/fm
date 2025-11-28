/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class BudgetDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            kpis: [],
            charts: [],
            loading: true,
            error: null,
            cost_centers: [],
            categories: [],
            filters: {
                period_type: 'month',
                cost_center_id: '',
                category_id: '',
                date_from: '',
                date_to: '',
            }
        });

        onWillStart(async () => {
            await this.loadFilters();
            await this.loadData();
        });

        onMounted(() => {
            if (!this.state.loading && this.state.charts.length > 0) {
                this.renderAllCharts();
            }
        });
    }

    async loadFilters() {
        try {
            this.state.cost_centers = await this.orm.searchRead(
                'facilities.cost.center',
                [],
                ['id', 'name'],
                { order: 'name' }
            );
            
            this.state.categories = await this.orm.searchRead(
                'facilities.expense.category',
                [],
                ['id', 'name'],
                { order: 'name' }
            );
        } catch (error) {
            console.error("Error loading filters:", error);
            this.state.cost_centers = [];
            this.state.categories = [];
        }
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            const filters = {
                period_type: this.state.filters.period_type,
                cost_center_id: this.state.filters.cost_center_id ? parseInt(this.state.filters.cost_center_id) : null,
                category_id: this.state.filters.category_id ? parseInt(this.state.filters.category_id) : null,
                date_from: this.state.filters.date_from || null,
                date_to: this.state.filters.date_to || null,
            };
            
            console.log("Loading budget dashboard data with filters:", filters);
            
            const data = await this.orm.call(
                'facilities.budget.dashboard',
                'get_dashboard_data_api',
                [],
                { filters: filters }
            );
            
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
            
            console.log("Budget dashboard data loaded:", data);
        } catch (error) {
            console.error("Budget dashboard error:", error);
            this.state.error = "Failed to load dashboard data: " + (error.message || error);
            this.notification.add(
                "Failed to load budget dashboard data",
                { type: 'danger' }
            );
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
        const canvas = document.getElementById(`budget_chart_${index}`);
        if (!canvas) {
            console.warn(`Canvas budget_chart_${index} not found`);
            return;
        }

        const ctx = canvas.getContext('2d');
        
        if (canvas.chart) {
            canvas.chart.destroy();
        }
        
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
                    legend: { 
                        position: 'top',
                        display: true
                    },
                    title: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'USD'
                                }).format(context.parsed.y || context.parsed);
                                return label;
                            }
                        }
                    }
                },
                scales: chartData.type === 'pie' || chartData.type === 'doughnut' ? {} : {
                    y: { 
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }

    async onKPIClick(kpiKey) {
        if (!kpiKey) return;
        
        console.log("KPI clicked:", kpiKey);
        
        try {
            const actionMap = {
                'total_budget': 'action_drilldown_total_budget',
                'total_actual': 'action_drilldown_total_actual',
                'total_variance': 'action_drilldown_total_actual',
                'budget_utilization': 'action_drilldown_total_actual',
                'over_budget_count': 'action_drilldown_over_budget',
                'under_budget_count': 'action_drilldown_total_budget',
                'remaining_budget': 'action_drilldown_total_budget',
                'variance_percentage': 'action_drilldown_total_actual',
            };
            
            const actionName = actionMap[kpiKey];
            if (!actionName) {
                console.log("No drilldown action defined for KPI:", kpiKey);
                return;
            }
            
            const params = [
                this.state.filters.date_from || null,
                this.state.filters.date_to || null,
                this.state.filters.cost_center_id ? parseInt(this.state.filters.cost_center_id) : null,
                this.state.filters.category_id ? parseInt(this.state.filters.category_id) : null,
            ];
            
            console.log("Calling action:", actionName, "with params:", params);
            
            const action = await this.orm.call(
                'facilities.budget.dashboard',
                actionName,
                params
            );
            
            if (action) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.error("KPI click error:", error);
            this.notification.add(
                "Failed to open drilldown view: " + (error.message || error),
                { type: 'danger' }
            );
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
        this.state.filters.date_from = '';
        this.state.filters.date_to = '';
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }
    
    async onCostCenterChange(event) {
        this.state.filters.cost_center_id = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }
    
    async onCategoryChange(event) {
        this.state.filters.category_id = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }
    
    async onDateFromChange(event) {
        this.state.filters.date_from = event.target.value;
        this.state.filters.period_type = 'custom';
        if (this.state.filters.date_to) {
            await this.loadData();
            if (!this.state.loading && this.state.charts.length > 0) {
                this.renderAllCharts();
            }
        }
    }
    
    async onDateToChange(event) {
        this.state.filters.date_to = event.target.value;
        this.state.filters.period_type = 'custom';
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
            cost_center_id: '',
            category_id: '',
            date_from: '',
            date_to: '',
        };
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) {
            this.renderAllCharts();
        }
    }
    
    async onExport() {
        try {
            this.notification.add("Exporting budget data...", { type: 'info' });
            // Export functionality can be added here
        } catch (error) {
            console.error("Export error:", error);
        }
    }
}

BudgetDashboard.template = "facilities_management.BudgetDashboardClient";

registry.category("actions").add("facilities_budget_dashboard", BudgetDashboard);


