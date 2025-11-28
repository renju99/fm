# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.tools import groupby as groupbyelem
from operator import itemgetter
import base64
import logging

_logger = logging.getLogger(__name__)


class ServiceRequestPortal(CustomerPortal):

    # Removed problematic /my route override that was causing logout issues
    # Users can still access service requests via /my/service-requests directly
    
    # Removed root route override - now handled by facilities_homepage_controller
    
    _items_per_page = 20
    
    @http.route(['/dashboard'], type='http', auth="user", website=True, sitemap=False)
    def portal_dashboard(self, **kw):
        """Main dashboard for logged-in users - service request overview"""
        values = self._prepare_portal_layout_values()
        
        # Ensure proper website context for portal templates
        values.update({
            'is_frontend': True,
            'is_frontend_multilang': True,
        })
        
        # Get service request statistics
        service_requests = request.env['facilities.service.request'].search([
            ('requester_id', '=', request.env.user.id)
        ])
        
        # Calculate statistics
        total_requests = len(service_requests)
        open_requests = len(service_requests.filtered(lambda req: req.state in ['submitted', 'in_progress', 'pending_approval', 'approved', 'on_hold']))
        resolved_requests = len(service_requests.filtered(lambda req: req.state in ['resolved', 'closed']))
        overdue_requests = len(service_requests.filtered(lambda req: req.is_overdue))
        
        # Get recent requests
        recent_requests = service_requests.sorted('request_date', reverse=True)[:5]
        
        # Get requests by status
        requests_by_status = {}
        for sr in service_requests:
            status = sr.state
            if status not in requests_by_status:
                requests_by_status[status] = 0
            requests_by_status[status] += 1
        
        values.update({
            'total_requests': total_requests,
            'open_requests': open_requests,
            'resolved_requests': resolved_requests,
            'overdue_requests': overdue_requests,
            'recent_requests': recent_requests,
            'requests_by_status': requests_by_status,
            'page_name': 'dashboard',
        })
        
        return request.render("facilities_management.portal_dashboard", values)
    
    def _prepare_home_portal_values(self, counters):
        """Add service request counts to portal home"""
        values = super()._prepare_home_portal_values(counters)
        
        # Always add service request count if user can access the model
        try:
            service_request_count = request.env['facilities.service.request'].search_count([
                ('requester_id', '=', request.env.user.id)
            ])
            values['service_request_count'] = service_request_count
        except:
            values['service_request_count'] = 0
        
        return values

    @http.route(['/service-requests'], type='http', auth="user", website=True)
    def service_requests_redirect(self, **kw):
        """Redirect /service-requests to /my/service-requests for logged-in users"""
        return request.redirect('/my/service-requests')

    @http.route(['/my/service-requests-test'], type='http', auth="user", website=True)
    def test_service_requests(self, **kw):
        """Test route to verify controller is working"""
        return "<h1>Service Request Portal Test - Controller Working!</h1>"

    def _prepare_portal_layout_values(self):
        """Prepare portal layout values with service request count"""
        values = super()._prepare_portal_layout_values()
        try:
            service_request_count = request.env['facilities.service.request'].search_count([
                ('requester_id', '=', request.env.user.id)
            ])
            values['service_request_count'] = service_request_count
        except:
            values['service_request_count'] = 0
        return values

    def _get_service_request_searchbar_sortings(self):
        """Get sorting options for service requests"""
        return {
            'date': {'label': _('Newest'), 'order': 'request_date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
            'status': {'label': _('Status'), 'order': 'state'},
            'priority': {'label': _('Priority'), 'order': 'priority desc'},
        }

    def _get_service_request_searchbar_filters(self):
        """Get filter options for service requests"""
        return {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Draft'), 'domain': [('state', '=', 'draft')]},
            'submitted': {'label': _('Submitted'), 'domain': [('state', '=', 'submitted')]},
            'in_progress': {'label': _('In Progress'), 'domain': [('state', '=', 'in_progress')]},
            'resolved': {'label': _('Resolved'), 'domain': [('state', '=', 'resolved')]},
            'closed': {'label': _('Closed'), 'domain': [('state', '=', 'closed')]},
        }

    def _get_service_request_searchbar_groupby(self):
        """Get groupby options for service requests"""
        return {
            'none': {'input': 'none', 'label': _('None'), 'order': 1},
            'status': {'input': 'status', 'label': _('Status'), 'order': 2},
            'service_type': {'input': 'service_type', 'label': _('Service Type'), 'order': 3},
            'priority': {'input': 'priority', 'label': _('Priority'), 'order': 4},
        }

    @http.route(['/my/service-requests', '/my/service-requests/page/<int:page>'], type='http', auth="user", website=True, sitemap=False)
    def portal_my_service_requests(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, groupby=None, search=None, **kw):
        """Portal page for tenant service requests"""
        values = self._prepare_portal_layout_values()
        ServiceRequest = request.env['facilities.service.request']

        domain = [('requester_id', '=', request.env.user.id)]

        searchbar_sortings = self._get_service_request_searchbar_sortings()
        searchbar_filters = self._get_service_request_searchbar_filters()
        searchbar_groupby = self._get_service_request_searchbar_groupby()

        # Default sort order
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Default filter
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # Default groupby
        if not groupby:
            groupby = 'none'

        # Search
        if search:
            search_domain = ['|', '|', ('name', 'ilike', search), ('title', 'ilike', search), ('description', 'ilike', search)]
            domain += search_domain

        # Date filtering
        if date_begin and date_end:
            domain += [('request_date', '>', date_begin), ('request_date', '<=', date_end)]

        # Count for pager
        service_request_count = ServiceRequest.search_count(domain)

        # Pager
        pager = portal_pager(
            url="/my/service-requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby, 'groupby': groupby, 'search': search},
            total=service_request_count,
            page=page,
            step=self._items_per_page
        )

        # Content according to pager and archive selected
        service_requests = ServiceRequest.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_service_requests_history'] = service_requests.ids[:100]

        # Groupby - simplified for now
        grouped_requests = [service_requests]

        values.update({
            'date': date_begin,
            'date_end': date_end,
            'service_requests': service_requests,
            'grouped_requests': grouped_requests,
            'page_name': 'service_request',
            'archive_groups': [],
            'default_url': '/my/service-requests',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_groupby': searchbar_groupby,
            'search': search,
            'searchbar_filters': searchbar_filters,
            'sortby': sortby,
            'filterby': filterby,
            'groupby': groupby,
        })
        return request.render("facilities_management.portal_my_service_requests", values)

    @http.route(['/my/service-request/<int:request_id>'], type='http', auth="user", website=True, sitemap=False)
    def portal_service_request_detail(self, request_id, access_token=None, **kw):
        """Portal page for service request details"""
        try:
            service_request_sudo = self._document_check_access('facilities.service.request', request_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = {
            'service_request': service_request_sudo,
            'page_name': 'service_request',
        }
        return request.render("facilities_management.portal_service_request_detail", values)

    @http.route(['/my/service-request/new'], type='http', auth="user", website=True, sitemap=False)
    def portal_service_request_new(self, **kw):
        """Portal page for creating new service request"""
        # Get available service catalog items
        service_catalog = request.env['facilities.service.catalog'].sudo().search([
            ('available', '=', True),
            ('active', '=', True)
        ])

        # Get user's facilities for location selection
        facilities = request.env['facilities.facility'].sudo().search([])
        buildings = request.env['facilities.building'].sudo().search([])
        floors = request.env['facilities.floor'].sudo().search([])
        rooms = request.env['facilities.room'].sudo().search([])

        values = {
            'service_catalog': service_catalog,
            'facilities': facilities,
            'buildings': buildings,
            'floors': floors,
            'rooms': rooms,
            'page_name': 'service_request_new',
        }
        return request.render("facilities_management.portal_service_request_new", values)

    @http.route(['/my/service-request/create'], type='http', auth="user", website=True, methods=['GET', 'POST'], csrf=True)
    def portal_service_request_create(self, room_id=None, **post):
        """Create new service request from portal (GET for QR code, POST for form submission)"""
        # Handle GET request (QR code scan)
        if request.httprequest.method == 'GET':
            room_data = None
            room = None
            
            if room_id:
                try:
                    room = request.env['facilities.room'].sudo().browse(int(room_id))
                    if room.exists():
                        room_data = room.get_room_data_from_qr(int(room_id))
                except (ValueError, TypeError):
                    pass

            # Get available service catalog items
            service_catalog = request.env['facilities.service.catalog'].sudo().search([
                ('available', '=', True),
                ('active', '=', True)
            ])

            # Get user's facilities for location selection
            facilities = request.env['facilities.facility'].sudo().search([])
            buildings = request.env['facilities.building'].sudo().search([])
            floors = request.env['facilities.floor'].sudo().search([])
            rooms = request.env['facilities.room'].sudo().search([])

            values = {
                'service_catalog': service_catalog,
                'facilities': facilities,
                'buildings': buildings,
                'floors': floors,
                'rooms': rooms,
                'room_data': room_data,
                'room': room,
                'page_name': 'service_request_create_from_qr',
                'is_qr_request': bool(room_id),
            }
            return request.render("facilities_management.portal_service_request_create_from_qr", values)
        
        # Handle POST request (form submission)
        try:
            # Handle catalog-based requests
            catalog_id = post.get('catalog_id')
            if catalog_id:
                catalog_item = request.env['facilities.service.catalog'].sudo().browse(int(catalog_id))
                if catalog_item.exists():
                    # Use catalog item information
                    title = post.get('title') or catalog_item.name
                    service_type = post.get('service_type') or catalog_item.category
                    description = post.get('description', '')
                    if catalog_item.description:
                        description = f"Service Request from Catalog: {catalog_item.name}\n\nService Description: {catalog_item.description}\n\nAdditional Details: {description}"
                else:
                    title = post.get('title')
                    service_type = post.get('service_type')
                    description = post.get('description')
            else:
                title = post.get('title')
                service_type = post.get('service_type')
                description = post.get('description')

            # Prepare values
            values = {
                'title': title,
                'description': description,
                'service_type': service_type,
                'priority': post.get('priority', '2'),
                'urgency': post.get('urgency', 'medium'),
                'contact_phone': post.get('contact_phone'),
                'contact_email': post.get('contact_email'),
                'requester_id': request.env.user.id,  # Portal user linking via email
                'state': 'submitted',  # Auto-submit from portal
            }

            # Add optional fields
            if post.get('category_id'):
                values['category_id'] = int(post.get('category_id'))
            if post.get('facility_id'):
                values['facility_id'] = int(post.get('facility_id'))
            if post.get('building_id'):
                values['building_id'] = int(post.get('building_id'))
            if post.get('floor_id'):
                values['floor_id'] = int(post.get('floor_id'))
            if post.get('room_id'):
                values['room_id'] = int(post.get('room_id'))

            # Create service request
            service_request = request.env['facilities.service.request'].sudo().create(values)
            
            # Creation notification is automatically sent by the model's create method for submitted records

            # Handle file attachments
            if post.get('attachment'):
                attachment_data = post.get('attachment')
                if hasattr(attachment_data, 'read'):
                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': attachment_data.filename,
                        'datas': base64.b64encode(attachment_data.read()),
                        'res_model': 'facilities.service.request',
                        'res_id': service_request.id,
                        'public': False,
                    })

            return request.redirect('/my/service-request/%s?message=created' % service_request.id)

        except Exception as e:
            return request.redirect('/my/service-request/new?error=%s' % str(e))

    @http.route(['/my/service-catalog'], type='http', auth="user", website=True)
    def portal_service_catalog(self, **kw):
        """Portal page for browsing service catalog"""
        try:
            # Get available service catalog items grouped by category
            service_catalog = request.env['facilities.service.catalog'].sudo().search([
                ('available', '=', True),
                ('active', '=', True)
            ], order='category, sequence, name')

            # If no services found, show empty catalog
            if not service_catalog:
                values = {
                    'service_catalog': [],
                    'catalog_by_category': {},
                    'page_name': 'service_catalog',
                }
                return request.render("facilities_management.portal_service_catalog", values)

            # Group by category
            catalog_by_category = {}
            for service in service_catalog:
                if service.category not in catalog_by_category:
                    catalog_by_category[service.category] = []
                catalog_by_category[service.category].append(service)

            values = {
                'service_catalog': service_catalog,
                'catalog_by_category': catalog_by_category,
                'page_name': 'service_catalog',
            }
            return request.render("facilities_management.portal_service_catalog", values)
        except Exception as e:
            return f"<h1>Error in service catalog: {str(e)}</h1>"

    @http.route(['/my/service-catalog/<int:catalog_id>/request'], type='http', auth="user", website=True)
    def portal_service_catalog_request(self, catalog_id, **kw):
        """Portal page for requesting a specific service from catalog"""
        try:
            catalog_item = request.env['facilities.service.catalog'].sudo().browse(catalog_id)
            if not catalog_item.exists() or not catalog_item.available or not catalog_item.active:
                return request.redirect('/my/service-catalog')

            # Get user's facilities for location selection
            facilities = request.env['facilities.facility'].sudo().search([])
            buildings = request.env['facilities.building'].sudo().search([])
            floors = request.env['facilities.floor'].sudo().search([])
            rooms = request.env['facilities.room'].sudo().search([])

            values = {
                'catalog_item': catalog_item,
                'facilities': facilities,
                'buildings': buildings,
                'floors': floors,
                'rooms': rooms,
                'page_name': 'service_request_from_catalog',
            }
            return request.render("facilities_management.portal_service_request_from_catalog", values)

        except Exception:
            return request.redirect('/my/service-catalog')

    @http.route(['/my/help-center'], type='http', auth="user", website=True)
    def portal_help_center(self, search=None, category=None, **kw):
        """Portal help center with documents and contacts"""
        # Get available documents
        domain = [('published', '=', True), ('active', '=', True)]
        if category:
            domain.append(('category', '=', category))
        if search:
            domain.extend([
                '|', '|', '|',
                ('name', 'ilike', search),
                ('description', 'ilike', search),
                ('content', 'ilike', search),
                ('keywords', 'ilike', search)
            ])

        documents = request.env['facilities.service.document'].sudo().search(domain, order='featured desc, sequence, name')
        
        # Get available contacts
        contacts = request.env['facilities.service.contact'].sudo().search([
            ('active', '=', True)
        ], order='priority_level, name')

        # Get document categories for filtering
        categories = request.env['facilities.service.document'].sudo().read_group(
            [('published', '=', True), ('active', '=', True)],
            ['category'],
            ['category']
        )

        values = {
            'documents': documents,
            'contacts': contacts,
            'categories': categories,
            'search': search,
            'current_category': category,
            'page_name': 'help_center',
        }
        return request.render("facilities_management.portal_help_center", values)

    @http.route(['/my/help-center/document/<int:document_id>'], type='http', auth="user", website=True)
    def portal_help_document(self, document_id, **kw):
        """View help center document"""
        try:
            document = request.env['facilities.service.document'].sudo().browse(document_id)
            if not document.exists() or not document.published or not document.active:
                return request.redirect('/my/help-center')

            # Increment view count
            document.sudo().write({
                'view_count': document.view_count + 1,
                'last_viewed': fields.Datetime.now()
            })

            values = {
                'document': document,
                'page_name': 'help_document',
            }
            return request.render("facilities_management.portal_help_document", values)

        except Exception:
            return request.redirect('/my/help-center')

    def _document_check_access(self, model_name, document_id, access_token=None):
        """Check access to document"""
        document = request.env[model_name].browse([document_id])
        document_sudo = document.sudo()
        
        try:
            document.check_access('read')
        except AccessError:
            if access_token and document_sudo.access_token and document_sudo.access_token == access_token:
                return document_sudo
            else:
                raise
        return document_sudo

    @http.route(['/service-request/attachment/<int:attachment_id>'], type='http', auth="user", website=True)
    def portal_service_request_attachment(self, attachment_id, **kw):
        """Download service request attachment"""
        try:
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if attachment.res_model == 'facilities.service.request':
                # Check if user owns the service request
                service_request = request.env['facilities.service.request'].sudo().browse(attachment.res_id)
                if service_request.requester_id.id == request.env.user.id:
                    return request.env['ir.http']._content_image(
                        xmlid=None, model='ir.attachment', res_id=attachment_id,
                        field='datas', filename_field='name', download=True
                    )
        except Exception:
            pass
        
        return request.not_found()

    @http.route(['/my/service-request/<int:request_id>/feedback'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_service_request_feedback(self, request_id, **post):
        """Submit feedback for completed service request"""
        try:
            service_request = request.env['facilities.service.request'].sudo().browse(request_id)
            if service_request.requester_id.id == request.env.user.id and service_request.state in ['resolved', 'closed']:
                service_request.write({
                    'feedback_rating': post.get('rating'),
                    'feedback_comments': post.get('comments'),
                })
                return request.redirect('/my/service-request/%s?message=feedback_submitted' % request_id)
        except Exception:
            pass
        
        return request.redirect('/my/service-requests')

    @http.route(['/api/buildings/<int:facility_id>'], type='json', auth="user", website=True)
    def get_buildings_for_facility(self, facility_id, **kw):
        """Get buildings for a facility (AJAX)"""
        buildings = request.env['facilities.building'].sudo().search([
            ('facility_id', '=', facility_id)
        ])
        return [{'id': b.id, 'name': b.name} for b in buildings]

    @http.route(['/api/floors/<int:building_id>'], type='json', auth="user", website=True)
    def get_floors_for_building(self, building_id, **kw):
        """Get floors for a building (AJAX)"""
        floors = request.env['facilities.floor'].sudo().search([
            ('building_id', '=', building_id)
        ])
        return [{'id': f.id, 'name': f.name} for f in floors]

    @http.route(['/api/rooms/<int:floor_id>'], type='json', auth="user", website=True)
    def get_rooms_for_floor(self, floor_id, **kw):
        """Get rooms for a floor (AJAX)"""
        rooms = request.env['facilities.room'].sudo().search([
            ('floor_id', '=', floor_id)
        ])
        return [{'id': r.id, 'name': r.name} for r in rooms]

    @http.route('/my/service-request/<int:service_request_id>/reopen', type='http', auth='user', website=True, methods=['POST'])
    def service_request_reopen(self, service_request_id, **kwargs):
        """Handle service request reopen from portal"""
        try:
            service_request = request.env['facilities.service.request'].sudo().browse(service_request_id)
            
            # Validate service request exists
            if not service_request.exists():
                _logger.error(f"Service request {service_request_id} not found")
                if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return request.make_json_response({'error': 'Service request not found'}, status=404)
                return request.render('facilities_management.portal_service_request_detail', {
                    'error': 'Service request not found.'
                })
            
            
            # Check if user can reopen this request - use portal-safe method
            current_user = request.env.user
            can_reopen = service_request.can_portal_user_reopen(current_user.id)
            
            if not can_reopen:
                _logger.warning(f"User {current_user.id} not authorized to reopen service request {service_request.id}. Requester: {service_request.requester_id.id}, State: {service_request.state}")
                error_msg = 'You are not authorized to reopen this service request. You can only reopen requests that you created.'
                if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return request.make_json_response({'error': error_msg}, status=403)
                return request.render('facilities_management.portal_service_request_detail', {
                    'service_request': service_request,
                    'error': error_msg
                })
            
            reopen_reason = kwargs.get('reopen_reason', '').strip()
            if not reopen_reason:
                error_msg = 'Please provide a reason for reopening the request.'
                if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return request.make_json_response({'error': error_msg}, status=400)
                return request.render('facilities_management.portal_service_request_detail', {
                    'service_request': service_request,
                    'error': error_msg
                })
            
            # Reopen the service request using sudo to avoid permission issues
            if service_request.action_reopen(reopen_reason):
                # Send notification email
                service_request._send_status_update_notification(service_request.state, 'submitted')
                
                # Success response
                success_msg = 'Service request has been successfully reopened.'
                _logger.info(f"Service request {service_request.id} successfully reopened by user {request.env.user.id}")
                
                if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return request.make_json_response({
                        'success': True,
                        'message': success_msg,
                        'redirect_url': '/my/service-request/%s?reopened=1' % service_request_id
                    })
                
                return request.redirect('/my/service-request/%s?reopened=1' % service_request_id)
            else:
                error_msg = 'Unable to reopen this service request. It may not be in a reopenable state.'
                if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return request.make_json_response({'error': error_msg}, status=400)
                return request.render('facilities_management.portal_service_request_detail', {
                    'service_request': service_request,
                    'error': error_msg
                })
                
        except Exception as e:
            _logger.error(f"Error reopening service request {service_request_id}: {str(e)}")
            error_msg = 'An error occurred while reopening the service request. Please try again or contact support.'
            if request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return request.make_json_response({'error': error_msg}, status=500)
            return request.render('facilities_management.portal_service_request_detail', {
                'service_request': service_request if 'service_request' in locals() else None,
                'error': error_msg
            })
