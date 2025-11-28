/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class MaintenanceDashboardBase extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            kpis: [],
            charts: [],
            loading: true,
            error: null,
            facilities: [],
            technicians: [],
            teams: [],
            filters: {
                period_type: 'month',
                facility_id: '',
                technician_id: '',
                team_id: '',
                priority: '',
                maintenance_type: '',
                date_from: '',
                date_to: '',
            }
        });

        onWillStart(async () => {
            await this.loadFilterOptions();
            await this.loadData();
        });

        onMounted(() => {
            if (!this.state.loading && this.state.charts.length > 0) {
                this.renderAllCharts();
            }
        });
    }

    async loadFilterOptions() {
        try {
            this.state.facilities = await this.orm.searchRead('facilities.facility', [], ['id', 'name'], { order: 'name' });
            this.state.technicians = await this.orm.searchRead('hr.employee', [], ['id', 'name'], { order: 'name', limit: 100 });
            this.state.teams = await this.orm.searchRead('maintenance.team', [], ['id', 'name'], { order: 'name' });
        } catch (error) {
            console.error("Error loading filter options:", error);
        }
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            const filters = this._prepareFilters();
            const data = await this.orm.call(
                'maintenance.analytics.dashboard',
                this.getApiMethod(),
                [],
                { filters: filters }
            );
            
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
        } catch (error) {
            console.error("Dashboard error:", error);
            this.state.error = "Failed to load dashboard data: " + error.message;
        } finally {
            this.state.loading = false;
        }
    }

    _prepareFilters() {
        const filters = { period_type: this.state.filters.period_type };
        
        if (this.state.filters.facility_id) filters.facility_id = parseInt(this.state.filters.facility_id);
        if (this.state.filters.technician_id) filters.technician_id = parseInt(this.state.filters.technician_id);
        if (this.state.filters.team_id) filters.team_id = parseInt(this.state.filters.team_id);
        if (this.state.filters.priority) filters.priority = this.state.filters.priority;
        if (this.state.filters.maintenance_type) filters.maintenance_type = this.state.filters.maintenance_type;
        if (this.state.filters.date_from) filters.date_from = this.state.filters.date_from;
        if (this.state.filters.date_to) filters.date_to = this.state.filters.date_to;
        
        return filters;
    }

    getApiMethod() {
        return 'get_kpi_dashboard_data'; // Override in subclasses
    }

    renderAllCharts() {
        setTimeout(() => {
            this.state.charts.forEach((chartData, index) => {
                this.renderChart(index, chartData);
            });
        }, 100);
    }

    renderChart(index, chartData) {
        const canvas = document.getElementById(`maint_chart_${index}`);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (canvas.chart) canvas.chart.destroy();
        
        canvas.chart = new Chart(ctx, {
            type: chartData.type,
            data: { labels: chartData.labels, datasets: chartData.datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: 'top' } },
                scales: (chartData.type === 'pie' || chartData.type === 'doughnut') ? {} : { y: { beginAtZero: true } }
            }
        });
    }

    async onRefresh() {
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onPeriodChange(event) {
        this.state.filters.period_type = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onFacilityChange(event) {
        this.state.filters.facility_id = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onTechnicianChange(event) {
        this.state.filters.technician_id = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onTeamChange(event) {
        this.state.filters.team_id = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onPriorityChange(event) {
        this.state.filters.priority = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onMaintenanceTypeChange(event) {
        this.state.filters.maintenance_type = event.target.value;
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }

    async onDateFromChange(event) {
        this.state.filters.date_from = event.target.value;
        if (this.state.filters.date_to) {
            await this.loadData();
            if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
        }
    }

    async onDateToChange(event) {
        this.state.filters.date_to = event.target.value;
        if (this.state.filters.date_from) {
            await this.loadData();
            if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
        }
    }

    async onClearFilters() {
        this.state.filters = {
            period_type: 'month',
            facility_id: '',
            technician_id: '',
            team_id: '',
            priority: '',
            maintenance_type: '',
            date_from: '',
            date_to: '',
        };
        await this.loadData();
        if (!this.state.loading && this.state.charts.length > 0) this.renderAllCharts();
    }
}

// KPI Dashboard
class MaintenanceKPIDashboard extends MaintenanceDashboardBase {
    getApiMethod() {
        return 'get_kpi_dashboard_data';
    }
}
MaintenanceKPIDashboard.template = "facilities_management.MaintenanceDashboardTemplate";
registry.category("actions").add("maintenance_kpi_dashboard", MaintenanceKPIDashboard);

// Technician Performance Dashboard
class TechnicianPerformanceDashboard extends MaintenanceDashboardBase {
    getApiMethod() {
        return 'get_technician_performance_data';
    }
}
TechnicianPerformanceDashboard.template = "facilities_management.MaintenanceDashboardTemplate";
registry.category("actions").add("technician_performance_dashboard", TechnicianPerformanceDashboard);

// Resource Utilization Dashboard
class ResourceUtilizationDashboard extends MaintenanceDashboardBase {
    getApiMethod() {
        return 'get_resource_utilization_data';
    }
}
ResourceUtilizationDashboard.template = "facilities_management.MaintenanceDashboardTemplate";
registry.category("actions").add("resource_utilization_dashboard", ResourceUtilizationDashboard);

// Maintenance Performance Dashboard
class MaintenancePerformanceDashboard extends MaintenanceDashboardBase {
    getApiMethod() {
        return 'get_maintenance_performance_data';
    }
}
MaintenancePerformanceDashboard.template = "facilities_management.MaintenanceDashboardTemplate";
registry.category("actions").add("maintenance_performance_dashboard", MaintenancePerformanceDashboard);

