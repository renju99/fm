# -*- coding: utf-8 -*-

from odoo import models, api, fields


class FacilityWorkOrderReport(models.AbstractModel):
    _name = 'report.fm.facility_workorder_report'
    _description = 'Facility Work Order Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get report values and ensure computed fields are computed"""
        # Check if we have wizard data with date range
        date_from = None
        date_to = None
        facility_id = None
        
        if data and isinstance(data, dict):
            date_from = data.get('date_from')
            date_to = data.get('date_to')
            facility_id = data.get('facility_id')
        
        # If we have a specific facility from wizard, use it; otherwise use docids
        if facility_id:
            docs = self.env['facilities.facility'].browse([facility_id])
        else:
            docs = self.env['facilities.facility'].browse(docids)
        
        # Ensure all computed fields are computed before rendering the template
        for doc in docs:
            doc.prepare_for_report()
        
        # Get work orders filtered by date range if provided
        # Initialize as empty recordset instead of list to maintain ORM methods
        workorders = self.env['facilities.workorder']
        
        if date_from and date_to:
            # Ensure dates are in the correct format for comparison
            if isinstance(date_from, str):
                date_from = fields.Date.from_string(date_from)
            if isinstance(date_to, str):
                date_to = fields.Date.from_string(date_to)
                
            for doc in docs:
                filtered_workorders = doc.get_facility_workorders().filtered(
                    lambda wo: wo.create_date and wo.create_date.date() >= date_from and wo.create_date.date() <= date_to
                )
                # Use union to maintain recordset structure instead of extend
                workorders = workorders | filtered_workorders
        else:
            for doc in docs:
                # Use union to maintain recordset structure instead of extend
                workorders = workorders | doc.get_facility_workorders()
        
        return {
            'doc_ids': docids,
            'doc_model': 'facilities.facility',
            'docs': docs,
            'data': data,
            'date_from': date_from,
            'date_to': date_to,
            'workorders': workorders,
        }