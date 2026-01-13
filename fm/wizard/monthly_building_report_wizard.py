from odoo import models, fields, api, _
from datetime import datetime, timedelta
import io, base64
import matplotlib.pyplot as plt
from collections import Counter, defaultdict
import calendar


class MonthlyBuildingReportWizard(models.TransientModel):
    _name = 'monthly.building.report.wizard'
    _description = 'Facility Maintenance Report Wizard'

    facility_id = fields.Many2one('facilities.facility', string='Facility', required=True)
    building_id = fields.Many2one('facilities.building', string='Building')
    # New multi-select filters
    facility_ids = fields.Many2many('facilities.facility', string='Facilities')
    floor_ids = fields.Many2many('facilities.floor', string='Floors')
    room_ids = fields.Many2many('facilities.room', string='Rooms')
    # Required custom date range
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise fields.ValidationError(_('Start Date must be before or equal to End Date.'))

    def action_generate_pdf_report(self):
        # Compute period from custom date range (inclusive of date_to)
        start_dt = datetime.combine(self.date_from, datetime.min.time())
        end_dt = datetime.combine(self.date_to + timedelta(days=1), datetime.min.time())
        period_label = f"{self.date_from.strftime('%Y-%m-%d')} to {self.date_to.strftime('%Y-%m-%d')}"
        days_in_period = (end_dt - start_dt).days
        hours_in_month = days_in_period * 24

        # Build domain with new filters (facility as primary)
        domain = [
            ('facility_id', '=', self.facility_id.id),
            ('create_date', '>=', start_dt),
            ('create_date', '<', end_dt),
        ]
        if self.building_id:
            domain.append(('building_id', '=', self.building_id.id))
        if self.facility_ids:
            domain.append(('facility_id', 'in', self.facility_ids.ids))
        if self.floor_ids:
            domain.append(('floor_id', 'in', self.floor_ids.ids))
        if self.room_ids:
            domain.append(('room_id', 'in', self.room_ids.ids))

        workorders = self.env['facilities.workorder'].search(domain)

        # Mappings for friendly names (aligned with actual model fields)
        STATUS_LABELS = {
            'draft': 'Draft',
            'assigned': 'Assigned',
            'in_progress': 'In Progress',
            'on_hold': 'On Hold',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
        }
        PRIORITY_LABELS = {
            '0': 'Very Low',
            '1': 'Low',
            '2': 'Normal',
            '3': 'High',
            '4': 'Critical',
        }
        TYPE_LABELS = {
            'corrective': 'Corrective',
            'preventive': 'Preventive',
            'predictive': 'Predictive',
            'inspection': 'Inspection',
        }
        SLA_LABELS = {
            'on_time': 'On Time',
            'at_risk': 'At Risk',
            'breached': 'Breached',
            'completed': 'Completed',
        }
        BUILDING_TYPE_LABELS = {
            'office': 'Office',
            'residential': 'Residential',
            'warehouse': 'Warehouse',
            'retail': 'Retail',
            'hospital': 'Hospital',
            'educational': 'Educational',
            'other': 'Other',
        }

        # Map technical to friendly names for counts
        status_counts = Counter(w.state for w in workorders)
        status_counts_friendly = Counter()
        for k, v in status_counts.items():
            status_counts_friendly[STATUS_LABELS.get(k, k)] = v

        type_counts = Counter(
            getattr(w, 'work_order_type', None) for w in workorders if getattr(w, 'work_order_type', None))
        type_counts_friendly = Counter()
        for k, v in type_counts.items():
            type_counts_friendly[TYPE_LABELS.get(k, k)] = v

        priority_counts = Counter(getattr(w, 'priority', '2') for w in workorders)
        priority_counts_friendly = Counter()
        for k, v in priority_counts.items():
            priority_counts_friendly[PRIORITY_LABELS.get(k, k)] = v

        # Aggregations
        asset_counts = Counter(w.asset_id.name for w in workorders if w.asset_id)
        room_counts = Counter(w.room_id.name for w in workorders if w.room_id)
        parts_counts = Counter()
        for wo in workorders:
            for part in getattr(wo, 'parts_used_ids', []):
                product_name = getattr(part, 'product_id', None) and part.product_id.name or 'Unknown'
                parts_counts[product_name] += getattr(part, 'quantity', 0)

        completion_times = []
        for wo in workorders:
            if (wo.state == 'completed' and
                    hasattr(wo, 'actual_start_date') and wo.actual_start_date and
                    hasattr(wo, 'actual_end_date') and wo.actual_end_date):
                completion_times.append((wo.actual_end_date - wo.actual_start_date).total_seconds() / 3600)
        avg_completion_time = round(sum(completion_times) / len(completion_times), 2) if completion_times else 0

        # SLA resolution statuses
        sla_status_counts = Counter()
        for w in workorders:
            sla_status = getattr(w, 'sla_resolution_status', None)
            if sla_status:
                sla_status_counts[sla_status] += 1

        sla_status_counts_friendly = Counter()
        for k, v in sla_status_counts.items():
            sla_status_counts_friendly[SLA_LABELS.get(k, k)] = v

        # Word frequency for issues
        desc_words = []
        for wo in workorders:
            description = getattr(wo, 'description', None)
            if description:
                desc_words += [w.lower() for w in description.split() if len(w) > 4]
        issue_counts = Counter(desc_words)

        # Daily counts
        day_counts = Counter()
        for wo in workorders:
            if hasattr(wo, 'create_date') and wo.create_date:
                day = (wo.create_date + timedelta(hours=0)).day
                day_counts[day] += 1

        top_assets = asset_counts.most_common(5)
        top_rooms = room_counts.most_common(5)
        top_parts = parts_counts.most_common(5)
        top_issues = issue_counts.most_common(5)

        def fig2base64(fig):
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode('utf-8')

        # Chart 1: Status Distribution (Pie)
        fig1, ax1 = plt.subplots()
        if status_counts_friendly:
            ax1.pie(list(status_counts_friendly.values()), labels=list(status_counts_friendly.keys()),
                    autopct='%1.1f%%')
        ax1.set_title("Work Order Status Distribution")
        chart_status = fig2base64(fig1)

        # Chart 2: Work Orders by Type (Bar)
        fig2, ax2 = plt.subplots()
        if type_counts_friendly:
            ax2.bar(type_counts_friendly.keys(), type_counts_friendly.values(), color='skyblue')
            plt.xticks(rotation=45)
        ax2.set_title("Work Orders by Type")
        chart_type = fig2base64(fig2)

        # Chart 3: Work Orders by Priority (Bar)
        fig3, ax3 = plt.subplots()
        if priority_counts_friendly:
            ax3.bar(priority_counts_friendly.keys(), priority_counts_friendly.values(), color='lightgreen')
            plt.xticks(rotation=45)
        ax3.set_title("Work Orders by Priority")
        chart_priority = fig2base64(fig3)

        # Chart 4: Top Assets (Barh)
        fig4, ax4 = plt.subplots()
        if top_assets:
            ax4.barh([a[0] for a in top_assets], [a[1] for a in top_assets], color='orange')
        ax4.set_title("Top 5 Assets with Most Work Orders")
        chart_assets = fig2base64(fig4)

        # Chart 5: Top Rooms (Barh)
        fig5, ax5 = plt.subplots()
        if top_rooms:
            ax5.barh([r[0] for r in top_rooms], [r[1] for r in top_rooms], color='purple')
        ax5.set_title("Top 5 Rooms with Most Work Orders")
        chart_rooms = fig2base64(fig5)

        # Chart 6: Top Parts (Barh)
        fig6, ax6 = plt.subplots()
        if top_parts:
            ax6.barh([p[0] for p in top_parts], [p[1] for p in top_parts], color='teal')
        ax6.set_title("Top 5 Parts Used")
        chart_parts = fig2base64(fig6)

        # Chart 7: Work Orders by Day (Line)
        fig7, ax7 = plt.subplots()
        days_sorted = sorted(day_counts.keys()) if day_counts else []
        if days_sorted:
            ax7.plot(days_sorted, [day_counts[d] for d in days_sorted], marker='o')
        ax7.set_title("Work Orders by Day")
        ax7.set_xlabel("Day of Period")
        ax7.set_ylabel("Work Orders")
        chart_days = fig2base64(fig7)

        # Chart 8: SLA Compliance (Pie)
        fig8, ax8 = plt.subplots()
        if sla_status_counts_friendly:
            ax8.pie(list(sla_status_counts_friendly.values()), labels=list(sla_status_counts_friendly.keys()),
                    autopct='%1.1f%%')
        ax8.set_title("SLA Compliance")
        chart_sla = fig2base64(fig8)

        # Chart 9: Wordcloud
        chart_wordcloud = None
        try:
            from wordcloud import WordCloud
            if desc_words:
                wc = WordCloud(width=400, height=200, background_color='white').generate(' '.join(desc_words))
                fig9 = plt.figure(figsize=(6, 3))
                plt.imshow(wc, interpolation='bilinear')
                plt.axis('off')
                chart_wordcloud = fig2base64(fig9)
        except ImportError:
            pass

        # Extended analytics for new HTML structure
        # KPIs
        total_workorders = len(workorders)
        completed_wos = workorders.filtered(lambda w: w.state == 'completed')

        # SLA compliance: consider not breached statuses among those with a status
        sla_total = sum(sla_status_counts.values()) if sla_status_counts else 0
        sla_compliant = sum(v for k, v in sla_status_counts.items() if k in ['on_time', 'completed'])
        sla_compliance_pct = round((sla_compliant / sla_total) * 100, 1) if sla_total else 0.0

        # Costs - handle missing fields gracefully
        total_cost = sum(getattr(w, 'total_cost', 0) or 0.0 for w in workorders)
        total_labor_cost = sum(getattr(w, 'labor_cost', 0) or 0.0 for w in workorders)
        total_parts_cost = sum(getattr(w, 'parts_cost', 0) or 0.0 for w in workorders)

        # Technicians
        technician_ids = set()
        for w in workorders:
            if hasattr(w, 'technician_ids') and w.technician_ids:
                for tech in w.technician_ids:
                    technician_ids.add(tech.id)
            elif hasattr(w, 'technician_id') and w.technician_id:
                technician_ids.add(w.technician_id.id)
        active_technicians = len(technician_ids)

        # Asset uptime approximation
        # number of unique assets in this result set
        unique_asset_ids = {w.asset_id.id for w in workorders if w.asset_id}
        num_assets = len(unique_asset_ids)
        total_possible_hours = (num_assets * hours_in_month) if num_assets else 0
        total_downtime_hours = sum(getattr(w, 'downtime_hours', 0) or 0.0 for w in workorders)
        asset_uptime_pct = 100.0
        if total_possible_hours > 0:
            asset_uptime_pct = max(0.0,
                                   min(100.0, round(100.0 * (1.0 - (total_downtime_hours / total_possible_hours)), 1)))

        # Critical issues and first-time fix
        critical_issues_count = sum(1 for w in workorders if getattr(w, 'priority', '2') == '4')
        ftf_numerator = sum(1 for w in completed_wos if getattr(w, 'first_time_fix', False))
        ftf_denominator = len(completed_wos)
        first_time_fix_rate = round((ftf_numerator / ftf_denominator) * 100, 1) if ftf_denominator else 0.0

        # Average resolution time (already computed)
        avg_resolution_hours = avg_completion_time

        # Trends vs previous period (previous period length)
        prev_start = start_dt - (end_dt - start_dt)
        prev_end = start_dt

        prev_domain = [
            ('facility_id', '=', self.facility_id.id),
            ('create_date', '>=', prev_start),
            ('create_date', '<', prev_end),
        ]
        if self.building_id:
            prev_domain.append(('building_id', '=', self.building_id.id))
        if self.facility_ids:
            prev_domain.append(('facility_id', 'in', self.facility_ids.ids))
        if self.floor_ids:
            prev_domain.append(('floor_id', 'in', self.floor_ids.ids))
        if self.room_ids:
            prev_domain.append(('room_id', 'in', self.room_ids.ids))

        prev_wos = self.env['facilities.workorder'].search(prev_domain)

        def pct_change(curr, prev):
            if prev == 0:
                return 0.0 if curr == 0 else 100.0
            return round(((curr - prev) * 100.0) / prev, 1)

        prev_total = len(prev_wos)
        prev_completed = prev_wos.filtered(lambda w: w.state == 'completed')

        prev_completion_times = []
        for w in prev_completed:
            if (hasattr(w, 'actual_start_date') and w.actual_start_date and
                    hasattr(w, 'actual_end_date') and w.actual_end_date):
                prev_completion_times.append((w.actual_end_date - w.actual_start_date).total_seconds() / 3600)
        prev_avg_resolution = round(sum(prev_completion_times) / len(prev_completion_times),
                                    2) if prev_completion_times else 0.0

        prev_sla_counts = Counter()
        for w in prev_wos:
            sla_status = getattr(w, 'sla_resolution_status', None)
            if sla_status:
                prev_sla_counts[sla_status] += 1

        prev_sla_total = sum(prev_sla_counts.values()) if prev_sla_counts else 0
        prev_sla_compliant = sum(v for k, v in prev_sla_counts.items() if k in ['on_time', 'completed'])
        prev_sla_pct = round((prev_sla_compliant / prev_sla_total) * 100, 1) if prev_sla_total else 0.0

        prev_total_cost = sum(getattr(w, 'total_cost', 0) or 0.0 for w in prev_wos)

        prev_technician_ids = set()
        for w in prev_wos:
            if hasattr(w, 'technician_ids') and w.technician_ids:
                for tech in w.technician_ids:
                    prev_technician_ids.add(tech.id)
            elif hasattr(w, 'technician_id') and w.technician_id:
                prev_technician_ids.add(w.technician_id.id)
        prev_techs = len(prev_technician_ids)

        prev_downtime = sum(getattr(w, 'downtime_hours', 0) or 0.0 for w in prev_wos)
        prev_possible_hours = len({w.asset_id.id for w in prev_wos if w.asset_id}) * (((prev_end - prev_start).days) * 24)
        prev_uptime_pct = 100.0 if prev_possible_hours == 0 else max(0.0, min(100.0, round(
            100.0 * (1.0 - (prev_downtime / prev_possible_hours)), 1)))

        prev_critical_count = sum(1 for w in prev_wos if getattr(w, 'priority', '2') == '4')
        prev_ftf_num = sum(
            1 for w in prev_wos.filtered(lambda w: w.state == 'completed') if getattr(w, 'first_time_fix', False))
        prev_ftf_den = len(prev_wos.filtered(lambda w: w.state == 'completed'))
        prev_ftf_rate = round((prev_ftf_num / prev_ftf_den) * 100, 1) if prev_ftf_den else 0.0

        # Daily trends for Chart.js
        daily_trends = []
        for d in sorted(day_counts.keys()):
            daily_trends.append({
                'date': d,
                'count': day_counts.get(d, 0),
            })

        # Floor performance (uptime by floor)
        floor_uptime = []
        downtime_by_floor = defaultdict(float)
        for w in workorders:
            if hasattr(w, 'floor_id') and w.floor_id:
                downtime_by_floor[w.floor_id.id] += (getattr(w, 'downtime_hours', 0) or 0.0)

        if downtime_by_floor:
            floors = self.env['facilities.floor'].browse(list(downtime_by_floor.keys()))
            for floor in floors:
                floor_assets = len(getattr(floor, 'asset_ids', [])) if hasattr(floor, 'asset_ids') else 1
                floor_possible = hours_in_month * floor_assets
                dt = downtime_by_floor.get(floor.id, 0.0)
                uptime = 100.0 if floor_possible == 0 else max(0.0, min(100.0,
                                                                        round(100.0 * (1.0 - (dt / floor_possible)),
                                                                              1)))
                floor_uptime.append({'label': floor.name, 'uptime': uptime})

        # Technician utilization (hours)
        tech_hours = defaultdict(float)
        for w in workorders:
            if hasattr(w, 'assignment_ids'):
                for assignment in w.assignment_ids:
                    if hasattr(assignment, 'technician_id') and assignment.technician_id:
                        tech_name = assignment.technician_id.name
                        work_hours = getattr(assignment, 'work_hours', 0) or 0.0
                        tech_hours[tech_name] += work_hours

        technician_utilization = sorted(
            [{'technician': k, 'hours': round(v, 2)} for k, v in tech_hours.items()],
            key=lambda x: x['hours'], reverse=True
        )[:15]
        total_technician_hours = round(sum(tech_hours.values()), 2)

        # Response time analysis
        response_times = []  # hours from create_date to actual_start_date
        for w in workorders:
            if (hasattr(w, 'create_date') and w.create_date and
                    hasattr(w, 'actual_start_date') and w.actual_start_date):
                response_times.append((w.actual_start_date - w.create_date).total_seconds() / 3600.0)

        avg_response_hours = round(sum(response_times) / len(response_times), 2) if response_times else 0.0

        # Buckets
        buckets = {'0-2h': 0, '2-4h': 0, '4-8h': 0, '>8h': 0}
        for h in response_times:
            if h < 2:
                buckets['0-2h'] += 1
            elif h < 4:
                buckets['2-4h'] += 1
            elif h < 8:
                buckets['4-8h'] += 1
            else:
                buckets['>8h'] += 1
        response_time_distribution = buckets

        # Cost breakdown
        cost_breakdown = {
            'Labor': round(total_labor_cost, 2),
            'Parts': round(total_parts_cost, 2),
        }
        other_cost = total_cost - (total_labor_cost + total_parts_cost)
        if abs(other_cost) > 0.005:
            cost_breakdown['Other'] = round(other_cost, 2)

        # Priority distribution with friendly labels order
        priority_distribution = {label: priority_counts_friendly.get(label, 0) for label in
                                 ['Critical', 'High', 'Normal', 'Low', 'Very Low']}

        # Critical assets table (top by downtime, fallback by work orders)
        asset_metrics = {}
        for w in workorders:
            if not w.asset_id:
                continue
            key = w.asset_id.id
            if key not in asset_metrics:
                asset_metrics[key] = {
                    'asset_id': w.asset_id,
                    'asset_name': w.asset_id.name,
                    'location': (w.asset_id.room_id and w.asset_id.room_id.display_name) or '',
                    'work_orders': 0,
                    'downtime_hours': 0.0,
                    'total_cost': 0.0,
                    'mttr_hours': [],
                    'priority_max': '0',
                }
            am = asset_metrics[key]
            am['work_orders'] += 1
            am['downtime_hours'] += (getattr(w, 'downtime_hours', 0) or 0.0)
            am['total_cost'] += (getattr(w, 'total_cost', 0) or 0.0)
            if hasattr(w, 'mttr') and w.mttr:
                am['mttr_hours'].append(w.mttr)
            # track highest priority
            w_priority = getattr(w, 'priority', '0')
            if w_priority and w_priority > am['priority_max']:
                am['priority_max'] = w_priority

        critical_assets_sorted = sorted(asset_metrics.values(), key=lambda x: (x['downtime_hours'], x['work_orders']),
                                        reverse=True)
        critical_assets = []
        for am in critical_assets_sorted[:18]:
            # next maintenance date from schedules (if any)
            next_maint = False
            if self.env.get('asset.maintenance.schedule'):
                schedules = self.env['asset.maintenance.schedule'].search([
                    ('asset_id', '=', am['asset_id'].id),
                    ('next_maintenance_date', '!=', False)
                ], order='next_maintenance_date asc', limit=1)
                if schedules:
                    next_maint = schedules.next_maintenance_date

            # asset health from condition
            condition = getattr(am['asset_id'], 'condition', 'good') or 'good'
            health_label = condition.capitalize()

            # map to classes used in HTML (excellent/good/fair/poor)
            condition_class = {
                'new': 'excellent',
                'good': 'good',
                'fair': 'fair',
                'poor': 'poor',
            }.get(condition, 'good')

            # priority label
            priority_label = PRIORITY_LABELS.get(am['priority_max'], 'Normal')
            critical_assets.append({
                'asset_name': am['asset_name'],
                'asset_display': f"{am['asset_name']}",
                'asset_code': getattr(am['asset_id'], 'asset_code', '') or '',
                'location': am['location'],
                'health_label': health_label,
                'health_class': condition_class,
                'work_orders': am['work_orders'],
                'downtime_hours': round(am['downtime_hours'], 1),
                'total_cost': round(am['total_cost'], 2),
                'mttr_hours': round(sum(am['mttr_hours']) / len(am['mttr_hours']), 2) if am['mttr_hours'] else 0.0,
                'next_maintenance': next_maint.strftime('%Y-%m-%d') if next_maint else '',
                'priority_label': priority_label,
                'priority_class': priority_label.lower(),
            })

        # Build data for QWeb and for new HTML consumers
        data = {
            # Legacy/template fields
            'total': total_workorders,
            'status_counts': status_counts_friendly,
            'type_counts': type_counts_friendly,
            'priority_counts': priority_counts_friendly,
            'top_assets': top_assets,
            'top_rooms': top_rooms,
            'top_parts': top_parts,
            'top_issues': top_issues,
            'avg_completion_time': avg_completion_time,
            'sla_status_counts': sla_status_counts_friendly,
            'chart_status': chart_status,
            'chart_type': chart_type,
            'chart_priority': chart_priority,
            'chart_assets': chart_assets,
            'chart_rooms': chart_rooms,
            'chart_parts': chart_parts,
            'chart_days': chart_days,
            'chart_sla': chart_sla,
            'chart_wordcloud': chart_wordcloud,
            'generated_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

            # New HTML-oriented structure
            'report_period': period_label,
            'facility_meta': {
                'id': self.facility_id.id,
                'name': self.facility_id.name,
            },
            'building_meta': {
                'id': self.building_id.id,
                'name': self.building_id.name,
                'code': getattr(self.building_id, 'code', '') or '',
                'address': getattr(self.building_id, 'address', '') or '',
                'facility': (hasattr(self.building_id, 'facility_id') and self.building_id.facility_id and self.building_id.facility_id.name) or '',
                'building_type': getattr(self.building_id, 'building_type', '') or '',
                'building_type_label': BUILDING_TYPE_LABELS.get(getattr(self.building_id, 'building_type', ''), ''),
                'number_of_floors': getattr(self.building_id, 'number_of_floors', 0) or 0,
                'floor_count': getattr(self.building_id, 'floor_count', 0) or 0,
                'total_area_sqm': getattr(self.building_id, 'total_area_sqm', 0) or 0,
                'year_constructed': getattr(self.building_id, 'year_constructed', 0) or 0,
                'manager': (hasattr(self.building_id,
                                    'manager_id') and self.building_id.manager_id and self.building_id.manager_id.name) or '',
            } if self.building_id else {},
            'kpis': {
                'total_workorders': total_workorders,
                'avg_resolution_hours': avg_resolution_hours,
                'sla_compliance_pct': sla_compliance_pct,
                'total_cost': round(total_cost, 2),
                'active_technicians': active_technicians,
                'asset_uptime_pct': asset_uptime_pct,
                'critical_issues_count': critical_issues_count,
                'first_time_fix_rate_pct': first_time_fix_rate,
                'trends': {
                    'total_workorders_pct': pct_change(total_workorders, prev_total),
                    'avg_resolution_hours_delta': round(avg_resolution_hours - prev_avg_resolution, 2),
                    'sla_compliance_pct_delta': round(sla_compliance_pct - prev_sla_pct, 1),
                    'total_cost_pct': pct_change(total_cost, prev_total_cost),
                    'active_technicians_delta': active_technicians - prev_techs,
                    'asset_uptime_pct_delta': round(asset_uptime_pct - prev_uptime_pct, 1),
                    'critical_issues_delta': critical_issues_count - prev_critical_count,
                    'first_time_fix_rate_pct_delta': round(first_time_fix_rate - prev_ftf_rate, 1),
                }
            },
            'charts': {
                'status_distribution': dict(status_counts_friendly),
                'maintenance_types': dict(type_counts_friendly),
                'priority_distribution': priority_distribution,
                'sla_performance': dict(sla_status_counts_friendly),
                'daily_trends': daily_trends,
                'floor_performance': floor_uptime,
                'cost_breakdown': cost_breakdown,
                'technician_utilization': technician_utilization,
                'response_time': {
                    'avg_hours': avg_response_hours,
                    'distribution': response_time_distribution,
                }
            },
            'critical_assets': critical_assets,
            'resources': {
                'total_technician_hours': total_technician_hours,
            },
        }

        return self.env.ref('fm.monthly_building_report_pdf_action').report_action(
            self,
            data={
                'doc': data,
                'data': {'doc': data},
                'form': data,
            },
        )