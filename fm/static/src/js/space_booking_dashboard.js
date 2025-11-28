/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState, onWillStart, onWillUnmount } from "@odoo/owl";

export class FacilitiesSpaceBookingDashboard extends Component {
	setup() {
		this.orm = useService("orm");
		this.notification = useService("notification");
		this.ui = useService("ui");

		this.state = useState({
			dashboardData: null,
			loading: true,
			error: null,
			selectedPeriod: 'current_month',
			selectedType: 'all',
			customDateFrom: null,
			customDateTo: null,
			showCustomDates: false,
			lastUpdated: null,
		});

		// Expose JSON to the template for JSON.stringify usage
		this.JSON = JSON;

		this.retryCount = 0;
		this.maxRetries = 3;
		this.retryTimeout = null;

		onWillStart(async () => {
			await this.loadDashboardData();
		});

		onMounted(() => {
			this.ensureScrolling();
			setTimeout(() => this.ensureScrolling(), 100);
			setTimeout(() => this.ensureScrolling(), 500);
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
		const container = document.querySelector('.o_space_booking_dashboard');
		if (container) {
			container.style.overflowY = 'auto';
			container.style.overflowX = 'hidden';
			container.style.height = 'auto';
			container.style.minHeight = 'auto';
			container.style.maxHeight = 'none';
			if (!container.style.scrollBehavior) container.style.scrollBehavior = 'smooth';
			if (!container.style.webkitOverflowScrolling) container.style.webkitOverflowScrolling = 'touch';
			container.offsetHeight;
		}
		const content = document.querySelector('.dashboard-content');
		if (content) {
			content.style.overflow = 'visible';
			content.style.height = 'auto';
		}
		const parentSelectors = ['.o_main_content', '.o_content', '.o_form_view', '.o_form_sheet', '.o_action_manager', '.o_view_manager_content', '.o_kanban_view', '.o_form_view_container'];
		const parent = container ? parentSelectors.map(s => container.closest(s)).find(Boolean) : null;
		if (parent) {
			parent.style.height = 'auto';
			parent.style.minHeight = 'auto';
			parent.style.maxHeight = 'none';
			parent.style.overflowY = 'auto';
			parent.style.overflowX = 'hidden';
		}
	}

	async loadDashboardData() {
		try {
			this.state.loading = true;
			this.state.error = null;
			const params = [this.state.selectedPeriod, this.state.selectedType];
			if (this.state.selectedPeriod === 'custom_range') {
				params.push(this.state.customDateFrom, this.state.customDateTo);
			}
			const data = await this.orm.call(
				'facilities.space.booking',
				'get_space_booking_dashboard_data',
				params
			);
			if (data && !data.error) {
				this.state.dashboardData = data;
				this.retryCount = 0;
				this.state.lastUpdated = new Date();
				setTimeout(() => this.ensureScrolling(), 10);
				setTimeout(() => this.ensureScrolling(), 250);
			} else {
				this.state.error = data?.error || 'Failed to load dashboard data';
				this.state.dashboardData = this.getDefaultData();
				this._handleError(this.state.error);
			}
		} catch (error) {
			this.state.error = this.getErrorMessage(error);
			this.state.dashboardData = this.getDefaultData();
			this._handleError(error);
		} finally {
			this.state.loading = false;
		}
	}

	getErrorMessage(error) {
		if (!error) return 'Unknown error';
		if (typeof error === 'string') return error;
		return error.message || 'Unknown error';
	}

	_isRetryableError(error) {
		return true;
	}

	_handleError(error) {
		const message = this.getErrorMessage(error);
		this.notification.add(`Dashboard Error: ${message}`, { type: 'danger', sticky: false });
		if (this.retryCount < this.maxRetries && this._isRetryableError(error)) {
			this.retryCount++;
			const delay = Math.min(1000 * Math.pow(2, this.retryCount), 10000);
			this.retryTimeout = setTimeout(() => this.loadDashboardData(), delay);
		}
	}

	getDefaultData() {
		return {
			period: this.state.selectedPeriod,
			summary: {
				total_bookings: 0,
				confirmed_bookings: 0,
				pending_approvals: 0,
				upcoming_week: 0,
				avg_capacity_utilization: 0,
				total_cost: 0,
			},
			trends: {
				bookings_per_day: [],
			},
			distribution: {
				by_type: {},
				by_room: {},
			},
			upcoming_bookings: [],
		};
	}

	async onPeriodChange(ev) {
		this.state.selectedPeriod = ev.target.value;
		this.state.showCustomDates = this.state.selectedPeriod === 'custom_range';
		await this.loadDashboardData();
	}

	async onTypeChange(ev) {
		this.state.selectedType = ev.target.value;
		await this.loadDashboardData();
	}

	async onRefreshClick() {
		await this.loadDashboardData();
	}

	async onRetryClick() {
		await this.loadDashboardData();
	}

	async onClearFiltersClick() {
		this.state.selectedPeriod = 'current_month';
		this.state.selectedType = 'all';
		this.state.customDateFrom = null;
		this.state.customDateTo = null;
		this.state.showCustomDates = false;
		await this.loadDashboardData();
	}

	formatNumber(value) {
		const numeric = Number(value || 0);
		return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(numeric);
	}

	formatDecimal(value, digits = 2) {
		const numeric = Number(value || 0);
		return new Intl.NumberFormat(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(numeric);
	}

	formatPercent(value) {
		const numeric = Number(value || 0);
		return `${this.formatDecimal(numeric, 1)}%`;
	}

	getUtilizationClass() {
		const utilization = Number(this.state.dashboardData?.summary?.avg_capacity_utilization || 0);
		if (utilization >= 80) return 'positive';
		if (utilization >= 50) return 'warning';
		return 'danger';
	}
}

FacilitiesSpaceBookingDashboard.template = 'facilities_space_booking_dashboard_template';
registry.category("actions").add("facilities_space_booking_dashboard", FacilitiesSpaceBookingDashboard);