/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState, onWillStart, onWillUnmount } from "@odoo/owl";

export class FacilitiesEnergyPerformanceDashboard extends Component {
    setup() {
        // Handle props defensively
        if (this.props.action !== undefined) {
            console.log("Facilities Energy Performance Dashboard: action received:", this.props.action);
            // Extract actionId from action object if needed
            if (this.props.action.id) {
                console.log("Facilities Energy Performance Dashboard: action ID:", this.props.action.id);
            }
        }
        
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.ui = useService("ui");
        
        this.state = useState({
            dashboardData: null,
            loading: true,
            error: null,
            selectedPeriod: 'current_year',
            selectedFacility: null,
            facilities: [],
            connectionStatus: 'connected',
            customDateFrom: null,
            customDateTo: null,
            showCustomDates: false
        });
        
        this.retryCount = 0;
        this.maxRetries = 3;
        this.retryTimeout = null;
        
        onWillStart(async () => {
            await this.loadFacilities();
            await this.loadDashboardData();
        });
        
        onMounted(() => {
            this.initializeCharts();
            this.ensureScrolling();
            
            // Additional scrolling enforcement after a short delay to ensure DOM is ready
            setTimeout(() => {
                this.ensureScrolling();
            }, 100);
            
            // Also ensure scrolling works after any dynamic content updates
            setTimeout(() => {
                this.ensureScrolling();
            }, 500);
        });
        
        onWillUnmount(() => {
            this._cleanup();
        });
    }

    _cleanup() {
        if (this.retryTimeout) {
            clearTimeout(this.retryTimeout);
            this.retryTimeout = null;
        }
    }

    ensureScrolling() {
        // Ensure scrolling functionality is properly set up
        const container = document.querySelector('.o_energy_performance_dashboard');
        if (container) {
            // Ensure proper overflow settings
            container.style.overflowY = 'auto';
            container.style.overflowX = 'hidden';
            container.style.height = 'auto';
            container.style.minHeight = 'auto';
            container.style.maxHeight = 'none';
            
            // Add smooth scrolling if not already present
            if (!container.style.scrollBehavior) {
                container.style.scrollBehavior = 'smooth';
            }
            
            // Add touch scrolling for mobile devices
            if (!container.style.webkitOverflowScrolling) {
                container.style.webkitOverflowScrolling = 'touch';
            }
            
            // Force reflow to ensure styles are applied
            container.offsetHeight;
        }
        
        // Also ensure the dashboard content is scrollable
        const content = document.querySelector('.dashboard-content');
        if (content) {
            content.style.overflow = 'visible';
            content.style.height = 'auto';
        }
        
        // Check for any parent containers that might be constraining height
        const possibleParents = [
            '.o_main_content',
            '.o_content', 
            '.o_form_view',
            '.o_form_sheet',
            '.o_action_manager',
            '.o_view_manager_content',
            '.o_kanban_view',
            '.o_form_view_container'
        ];
        
        possibleParents.forEach(selector => {
            const parent = container?.closest(selector);
            if (parent) {
                parent.style.height = 'auto';
                parent.style.minHeight = 'auto';
                parent.style.maxHeight = 'none';
                parent.style.overflowY = 'auto';
                parent.style.overflowX = 'hidden';
            }
        });
        
        // Specifically handle the immediate parent of the dashboard
        if (container && container.parentElement) {
            const immediateParent = container.parentElement;
            immediateParent.style.height = 'auto';
            immediateParent.style.minHeight = 'auto';
            immediateParent.style.maxHeight = 'none';
            immediateParent.style.overflowY = 'auto';
            immediateParent.style.overflowX = 'hidden';
        }
        
        console.log('Scrolling enforcement applied to energy performance dashboard');
    }

    async loadFacilities() {
        try {
            const facilities = await this.orm.searchRead(
                'facilities.facility',
                [],
                ['id', 'name']
            );
            this.state.facilities = facilities;
        } catch (error) {
            console.error("Error loading facilities:", error);
            this.state.facilities = [];
        }
    }

    async loadDashboardData() {
        try {
            this.state.loading = true;
            this.state.error = null;
            
            console.log("Facilities Energy Performance Dashboard: Loading data for period:", this.state.selectedPeriod);
            
            // Prepare parameters for the RPC call
            const params = [this.state.selectedPeriod];
            
            // Add facility_id parameter
            params.push(this.state.selectedFacility);
            
            // Add custom dates if custom_range is selected
            if (this.state.selectedPeriod === 'custom_range') {
                params.push(this.state.customDateFrom, this.state.customDateTo);
            } else {
                params.push(null, null); // Add null placeholders for date_from, date_to
            }
            
            const data = await this.orm.call(
                'facilities.energy.performance.dashboard',
                'get_comprehensive_dashboard_data',
                params
            );
            
            if (data && !data.error) {
                console.log("Facilities Energy Performance Dashboard: Successfully loaded data:", data);
                this.state.dashboardData = data;
                this.retryCount = 0; // Reset retry count on success
                // Ensure scrolling works after data is loaded and DOM is updated
                setTimeout(() => {
                    this.ensureScrolling();
                }, 10);
                // Additional enforcement for complex layouts
                setTimeout(() => {
                    this.ensureScrolling();
                }, 250);
            } else {
                console.error("Facilities Energy Performance Dashboard: Server returned error:", data?.error);
                this.state.error = data?.error || 'Failed to load dashboard data';
                this.state.dashboardData = this.getDefaultData();
                this._handleError(data?.error || 'Unknown server error');
            }
            
        } catch (error) {
            console.error("Facilities Energy Performance Dashboard: Error loading data:", error);
            this.state.error = this.getErrorMessage(error);
            this.state.dashboardData = this.getDefaultData();
            this._handleError(error);
        } finally {
            this.state.loading = false;
        }
    }

    _handleError(error) {
        const errorMessage = this.getErrorMessage(error);
        
        // Show user-friendly notification
        this.notification.add(
            `Dashboard Error: ${errorMessage}`,
            { type: 'danger', sticky: false }
        );
        
        // Retry logic for recoverable errors
        if (this.retryCount < this.maxRetries && this._isRetryableError(error)) {
            this.retryCount++;
            const retryDelay = Math.min(1000 * Math.pow(2, this.retryCount), 10000); // Exponential backoff
            
            console.log(`Facilities Energy Performance Dashboard: Retrying in ${retryDelay}ms (attempt ${this.retryCount}/${this.maxRetries})`);
            
            this.retryTimeout = setTimeout(() => {
                this.loadDashboardData();
            }, retryDelay);
        } else if (this.retryCount >= this.maxRetries) {
            console.error("Facilities Energy Performance Dashboard: Max retries reached");
            this.notification.add(
                "Failed to load dashboard data after multiple attempts. Please refresh the page.",
                { type: 'danger', sticky: true }
            );
        }
    }

    _isRetryableError(error) {
        // Don't retry on validation errors or permission errors
        const nonRetryableErrors = [
            'permission',
            'validation',
            'not found'
        ];
        
        const errorStr = error.toString().toLowerCase();
        return !nonRetryableErrors.some(nonRetryable => errorStr.includes(nonRetryable));
    }

    getDefaultData() {
        return {
            period: this.state.selectedPeriod,
            facility_id: this.state.selectedFacility,
            metrics: {
                total_meters: 0,
                total_consumption: 0.0,
                total_energy_cost: 0.0,
                avg_efficiency_score: 0.0,
                electricity_consumption: 0.0,
                water_consumption: 0.0,
                gas_consumption: 0.0,
                steam_consumption: 0.0,
                electricity_cost: 0.0,
                water_cost: 0.0,
                gas_cost: 0.0,
                steam_cost: 0.0,
                energy_efficiency_score: 0.0,
                water_efficiency_score: 0.0,
                sustainability_score: 0.0,
                co2_emissions: 0.0,
                peak_demand: 0.0,
                average_demand: 0.0,
                load_factor: 0.0,
                utilization_rate: 0.0,
                cost_per_sqm: 0.0,
                cost_per_occupant: 0.0,
                cost_per_hour: 0.0
            },
            trends: {
                consumption_trend: 'stable',
                trend_percentage: 0.0,
                cost_trend: 'stable',
                consumption_history: [],
                cost_history: []
            },
            alerts: {
                total_alerts: 0,
                high_consumption_alerts: 0,
                cost_anomaly_alerts: 0,
                maintenance_alerts: 0
            },
            benchmark: {
                benchmark_performance: 'average',
                industry_benchmark_cost: 0.0,
                cost_per_sqm: 0.0
            },
            summary: {
                total_meters: 0,
                total_alerts: 0,
                last_updated: new Date().toLocaleString()
            }
        };
    }

    getErrorMessage(error) {
        if (typeof error === 'string') {
            return error;
        } else if (error && error.message) {
            return error.message;
        } else if (error && error.data && error.data.message) {
            return error.data.message;
        } else if (error && error.data && error.data.debug) {
            return error.data.debug;
        } else {
            return 'An unexpected error occurred while loading dashboard data.';
        }
    }

    initializeCharts() {
        // Initialize charts when dashboard data is available
        if (this.state.dashboardData && this.state.dashboardData.trends) {
            this.renderCharts();
        }
    }

    renderCharts() {
        // Render charts using the trends data
        const trends = this.state.dashboardData.trends;
        
        // Consumption Trend Chart
        if (trends.consumption_history && trends.consumption_history.length > 0) {
            this.renderConsumptionChart(trends.consumption_history);
        }
        
        // Cost Trend Chart
        if (trends.cost_history && trends.cost_history.length > 0) {
            this.renderCostChart(trends.cost_history);
        }
        
        // Energy Type Breakdown Chart
        this.renderEnergyTypeChart();
        
        // Efficiency Metrics Chart
        this.renderEfficiencyChart();
    }

    renderConsumptionChart(data) {
        // Simple chart rendering - in a real implementation, you might use Chart.js or similar
        console.log("Rendering Consumption Chart with data:", data);
    }

    renderCostChart(data) {
        console.log("Rendering Cost Chart with data:", data);
    }

    renderEnergyTypeChart() {
        console.log("Rendering Energy Type Breakdown Chart");
    }

    renderEfficiencyChart() {
        console.log("Rendering Efficiency Metrics Chart");
    }

    async onPeriodChange(period) {
        this.state.selectedPeriod = period;
        this.state.showCustomDates = (period === 'custom_range');
        
        // Set default dates for custom range if not already set
        if (period === 'custom_range' && !this.state.customDateFrom) {
            const today = new Date();
            const startOfYear = new Date(today.getFullYear(), 0, 1);
            this.state.customDateFrom = startOfYear.toISOString().split('T')[0];
            this.state.customDateTo = today.toISOString().split('T')[0];
        }
        
        this.retryCount = 0; // Reset retry count for new period
        await this.loadDashboardData();
    }

    async onFacilityChange(facilityId) {
        this.state.selectedFacility = facilityId ? parseInt(facilityId) : null;
        this.retryCount = 0; // Reset retry count for new facility
        await this.loadDashboardData();
    }

    async onCustomDateFromChange(date) {
        this.state.customDateFrom = date;
        if (this.state.selectedPeriod === 'custom_range') {
            this.retryCount = 0;
            await this.loadDashboardData();
        }
    }

    async onCustomDateToChange(date) {
        this.state.customDateTo = date;
        if (this.state.selectedPeriod === 'custom_range') {
            this.retryCount = 0;
            await this.loadDashboardData();
        }
    }

    async refreshData() {
        this.retryCount = 0; // Reset retry count for manual refresh
        await this.loadDashboardData();
    }

    exportData() {
        if (!this.state.dashboardData) {
            this.notification.add("No data available to export", { type: 'warning' });
            return;
        }

        const data = this.state.dashboardData;
        const csvContent = this.convertToCSV(data);
        
        // Generate filename based on period or date range
        let filename;
        if (this.state.selectedPeriod === 'custom_range' && this.state.customDateFrom && this.state.customDateTo) {
            filename = `facilities_energy_performance_report_${this.state.customDateFrom}_to_${this.state.customDateTo}.csv`;
        } else {
            filename = `facilities_energy_performance_report_${this.state.selectedPeriod}.csv`;
        }
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.notification.add("Data exported successfully", { type: 'success' });
    }

    convertToCSV(data) {
        const metrics = data.metrics || {};
        const rows = [
            ['Metric', 'Value', 'Period', 'Facility ID']
        ];

        for (const [key, value] of Object.entries(metrics)) {
            rows.push([
                key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                value,
                data.period,
                data.facility_id || 'All'
            ]);
        }

        return rows.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    }

    formatPercentage(value) {
        return `${value.toFixed(2)}%`;
    }

    formatNumber(value) {
        return new Intl.NumberFormat('en-US').format(value);
    }

    formatConsumption(value, unit = 'kWh') {
        return `${this.formatNumber(value)} ${unit}`;
    }

    getTrendIcon(trend) {
        switch (trend) {
            case 'increasing':
                return '↗';
            case 'decreasing':
                return '↘';
            case 'stable':
                return '→';
            case 'fluctuating':
                return '↕';
            default:
                return '→';
        }
    }

    getTrendColor(trend) {
        switch (trend) {
            case 'increasing':
                return 'text-danger';
            case 'decreasing':
                return 'text-success';
            case 'stable':
                return 'text-info';
            case 'fluctuating':
                return 'text-warning';
            default:
                return 'text-secondary';
        }
    }

    getBenchmarkColor(performance) {
        switch (performance) {
            case 'excellent':
                return 'text-success';
            case 'good':
                return 'text-info';
            case 'average':
                return 'text-secondary';
            case 'below_average':
                return 'text-warning';
            case 'poor':
                return 'text-danger';
            default:
                return 'text-secondary';
        }
    }
}

FacilitiesEnergyPerformanceDashboard.template = 'facilities_energy_performance_dashboard_template';

// Register the dashboard component
registry.category("actions").add("facilities_energy_performance_dashboard", FacilitiesEnergyPerformanceDashboard);
