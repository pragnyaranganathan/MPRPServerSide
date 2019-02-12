from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
from frappe.utils import flt, getdate, datetime
from erpnext.stock.utils import get_latest_stock_qty
from erpnext.stock.get_item_details import get_batch_qty
from erpnext.stock.doctype.batch.batch import get_batch_no
from erpnext.stock.doctype.batch.batch import get_batches
from erpnext.stock.get_item_details import get_serial_no
import json


@frappe.whitelist()
def set_issued_items_from_stock_details(loggedInUser,issuedItemsFromStockList):
	
	item_details_list = []
	record = frappe.db.sql("""select usr.role_profile_name from `tabUser` usr where usr.name = %s""",(loggedInUser))
	if record:
		cdrecord = frappe.db.sql("""select cd.name, cd.warehouse, cd.upstream_warehouse, cd.downstream_warehouse from `tabControlDocument` cd where cd.user =%s and cd.docstatus = 1 and cd.is_active = 1 and cd.is_default = 1""",(record[0]))
		if cdrecord:
			company = frappe.defaults.get_user_default("Company")
			purposeType = "Material Transfer"
			warehouse = cdrecord[0][1]
			upstream_warehouse = cdrecord[0][2]
			#downstream_warehouse = cdrecord[0][3]
			newJson = {
					"company": company,
					"docType": "Stock Entry",
					"title"  : purposeType,
					"purpose": purposeType,
					"items"  :[
						  ]
				 }	
			data = json.loads(issuedItemsFromStockList)
			for jsonobj in data['issueMaterialFromStockDetailsModelList']:
				item_issued_json_list = get_the_item_issued_json(jsonobj, warehouse)
				if item_issued_json_list is not None:
					for  item  in item_issued_json_list:
						newJson["items"].append(item)
				else:
					return """Error: Something went wrong while entering the items in the Stock Entry document, Could not create a stock entry document on ERPNext""".encode('ascii')
			doc = frappe.new_doc("Stock Entry")
			doc.update(newJson)
			doc.save()
			doc.submit()
			frappe.db.commit()
			return """Success: Items have been succesfully issued and Stock Entry document has been created"""
		else:
			return """Error: Could not find the control document for the user {usr}""".format(usr = loggedInUser).encode('ascii')
	else:
		return """Error: Could not find the user {usr} on ERPNext. Please make sure the user credentials are correct""".format(usr = loggedInUser).encode('ascii')

def get_the_item_issued_json(item_consumed, warehouse):
	
	item_consumed_code = item_consumed['itemCode']
	item_consumed_qty = item_consumed['issuedQty']
	item_consumed_stock_uom = item_consumed['stockUOM']
	target_warehouse = item_consumed['selectedDownstreamWH']
	item_consumed_json_list = []
	selected_sln_list = []
	selected_batch_list = []
	
	if item_consumed['hasSerialNos']:
		if item_consumed['serialNoModelList'] is not None:
			for sln in item_consumed['serialNoModelList']:
				if sln['selected']:
					selected_sln_list.append(sln)
	
	if item_consumed['hasBatchNos']:
		item_consumed_batch_list = item_consumed['batchNoModelList']
		if len(item_consumed_batch_list) == 1:
			item_consumed_json = {
						"doctype": "Stock Entry Detail",
						"item_code": item_consumed_code,
						"description": item_consumed_code,
						"uom": item_consumed_stock_uom,
						"qty": item_consumed_qty,
						"s_warehouse": warehouse,
						"t_warehouse": target_warehouse,
						"batch_no": item_consumed_batch_list[0]['batchNo']
					     }
			if item_consumed['hasSerialNos'] and selected_sln_list:
				slns = " "
				for i in range(int(item_consumed_qty)):
					slns = slns+selected_sln_list[i]['serialNo']+'\n'
				item_consumed_json["serial_no"] = slns
			item_consumed_json_list.append(item_consumed_json)
		elif len(item_consumed_batch_list) > 1:
			for batch in item_consumed_batch_list:
				if batch['selected']:
					item_consumed_json = {
								"doctype": "Stock Entry Detail",
								"item_code": item_consumed_code,
								"description": item_consumed_code,
								"uom": item_consumed_stock_uom,
								"qty": batch['requestedBatchQty'],
								"s_warehouse":warehouse,
								"t_warehouse": target_warehouse,
								"batch_no": batch['batchNo']
							    }
					if item_consumed['hasSerialNos'] and selected_sln_list is not None:
						batchslnlist = getbatchwiseserialnos(batch['batchNo'],warehouse,item_consumed_code)
						count =0
						slns = " "
						for serial_No in selected_sln_list:
							if serial_No['serialNo'] in batchslnlist and count < int(batch['requestedBatchQty']):
								slns = slns+serial_No['serialNo']+'\n'
								count = count + 1
						item_consumed_json["serial_no"] = slns
					item_consumed_json_list.append(item_consumed_json)
		else:
			return None
	else:
		item_consumed_json = {
			"doctype": "Stock Entry Detail",
			"item_code": item_consumed_code,
			"description": item_consumed_code,
			"uom": item_consumed_stock_uom,
			"qty": item_consumed_qty,
			"s_warehouse": warehouse,
			"t_warehouse": target_warehouse
		     }
		if item_consumed['hasSerialNos'] and selected_sln_list is not None:
			slnos = " "
			for i in range(int(item_consumed_qty)):
				slnos = slnos+selected_sln_list[i]['serialNo']+'\n'
			item_consumed_json["serial_no"] = slnos
		item_consumed_json_list.append(item_consumed_json)
	if item_consumed_json_list is not None:
		return item_consumed_json_list
	else:
		return None

@frappe.whitelist()
def getbatchwiseserialnos(batch_no,warehouse,item_code):

	slnlist = []
	records = frappe.db.sql("""select sle.serial_no from `tabStock Ledger Entry` sle where sle.item_code = %(str1)s and sle.batch_no = %(str2)s and sle.warehouse = %(wh)s""",{'str1': item_code, 'str2': batch_no, 'wh':warehouse })
	if records:
		for record in records:
			
			data = record[0].split('\n')
			for i in range(0,len(data)):
				snrecord = frappe.db.sql("""select sn.name from `tabSerial No` sn where sn.serial_no = %(sln)s and sn.warehouse = %(wh)s""", {'sln': data[i], 'wh': warehouse})
				for slno in snrecord:
					serialno = slno[0].encode('ascii')
					slnlist.append(serialno)
		return slnlist

