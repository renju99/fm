# -*- coding: utf-8 -*-

from odoo import models, api, fields
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class SafetyIncidentReport(models.AbstractModel):
    _name = 'report.facilities_management.safety_incident_report'
    _description = 'Safety Incident Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values and ensure computed fields are computed"""
        # Get incidents from docids
        incidents = self.env['facilities.safety.incident'].browse(docids)
        
        # Ensure all computed fields are computed before rendering the template
        for incident in incidents:
            # Force computation of computed fields
            incident._compute_total_cost()
        
        # Get additional data for statistics
        company = self.env.company
        currency = company.currency_id
        
        # Calculate statistics for the report period
        stats = self._calculate_incident_statistics(incidents)
        
        # Get corrective actions for all incidents
        corrective_actions = self.env['facilities.incident.corrective.action'].search([
            ('incident_id', 'in', incidents.ids)
        ])
        
        # Group corrective actions by incident
        actions_by_incident = {}
        for action in corrective_actions:
            if action.incident_id.id not in actions_by_incident:
                actions_by_incident[action.incident_id.id] = []
            actions_by_incident[action.incident_id.id].append(action)
        
        return {
            'doc_ids': docids,
            'doc_model': 'facilities.safety.incident',
            'docs': incidents,
            'data': data,
            'company': company,
            'currency': currency,
            'stats': stats,
            'actions_by_incident': actions_by_incident,
            'current_date': fields.Date.today(),
            'current_datetime': fields.Datetime.now(),
        }
    
    def _calculate_incident_statistics(self, incidents):
        """Calculate statistics for the incidents in the report"""
        if not incidents:
            return {
                'total_incidents': 0,
                'injury_incidents': 0,
                'near_miss_incidents': 0,
                'property_damage_incidents': 0,
                'critical_incidents': 0,
                'high_severity_incidents': 0,
                'total_cost': 0,
                'average_cost': 0,
                'by_severity': {},
                'by_type': {},
                'by_facility': {},
                'by_status': {},
            }
        
        # Basic counts
        total_incidents = len(incidents)
        injury_incidents = len(incidents.filtered(lambda i: i.incident_type == 'injury'))
        near_miss_incidents = len(incidents.filtered(lambda i: i.incident_type == 'near_miss'))
        property_damage_incidents = len(incidents.filtered(lambda i: i.incident_type == 'property_damage'))
        critical_incidents = len(incidents.filtered(lambda i: i.severity == 'critical'))
        high_severity_incidents = len(incidents.filtered(lambda i: i.severity == 'high'))
        
        # Cost calculations
        total_cost = sum(incidents.mapped('total_cost'))
        average_cost = total_cost / total_incidents if total_incidents > 0 else 0
        
        # Group by severity
        by_severity = {}
        for severity in ['low', 'medium', 'high', 'critical']:
            by_severity[severity] = len(incidents.filtered(lambda i: i.severity == severity))
        
        # Group by type
        by_type = {}
        incident_types = ['injury', 'near_miss', 'property_damage', 'environmental', 'fire', 'chemical_spill', 'equipment_failure', 'security', 'other']
        for incident_type in incident_types:
            by_type[incident_type] = len(incidents.filtered(lambda i: i.incident_type == incident_type))
        
        # Group by facility
        by_facility = {}
        for incident in incidents:
            facility_name = incident.facility_id.name if incident.facility_id else 'Unknown'
            if facility_name not in by_facility:
                by_facility[facility_name] = 0
            by_facility[facility_name] += 1
        
        # Group by status
        by_status = {}
        for status in ['reported', 'under_investigation', 'pending_actions', 'closed']:
            by_status[status] = len(incidents.filtered(lambda i: i.state == status))
        
        return {
            'total_incidents': total_incidents,
            'injury_incidents': injury_incidents,
            'near_miss_incidents': near_miss_incidents,
            'property_damage_incidents': property_damage_incidents,
            'critical_incidents': critical_incidents,
            'high_severity_incidents': high_severity_incidents,
            'total_cost': total_cost,
            'average_cost': average_cost,
            'by_severity': by_severity,
            'by_type': by_type,
            'by_facility': by_facility,
            'by_status': by_status,
        }
    
    def _format_currency(self, amount, currency):
        """Format currency amount for display"""
        if not amount:
            return "0.00"
        return f"{amount:,.2f} {currency.symbol}"
    
    def _get_severity_color(self, severity):
        """Get color code for severity level"""
        colors = {
            'low': '#16a34a',      # Green
            'medium': '#ca8a04',   # Yellow
            'high': '#ea580c',     # Orange
            'critical': '#dc2626', # Red
        }
        return colors.get(severity, '#6b7280')
    
    def _get_severity_label(self, severity):
        """Get display label for severity level"""
        labels = {
            'low': 'Low',
            'medium': 'Medium',
            'high': 'High',
            'critical': 'Critical',
        }
        return labels.get(severity, 'Unknown')
    
    def _get_incident_type_label(self, incident_type):
        """Get display label for incident type"""
        labels = {
            'injury': 'Personal Injury',
            'near_miss': 'Near Miss',
            'property_damage': 'Property Damage',
            'environmental': 'Environmental Incident',
            'fire': 'Fire Incident',
            'chemical_spill': 'Chemical Spill',
            'equipment_failure': 'Equipment Failure',
            'security': 'Security Incident',
            'other': 'Other',
        }
        return labels.get(incident_type, 'Unknown')
    
    def _get_state_label(self, state):
        """Get display label for incident state"""
        labels = {
            'reported': 'Reported',
            'under_investigation': 'Under Investigation',
            'pending_actions': 'Pending Actions',
            'closed': 'Closed',
        }
        return labels.get(state, 'Unknown')
