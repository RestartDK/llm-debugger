"""
Dummy CFG + source fixture used to prototype the block tracing workflow.
"""
from __future__ import annotations

from textwrap import dedent
from typing import Dict, List, Tuple

from .debug_types import BasicBlock, build_exit_line_lookup


DUMMY_SOURCE_FILES: Dict[str, str] = {
    "ecommerce/orders.py": dedent(
        """
        def calculate_item_total(items):
            subtotal = 0.0
            item_details = []
            for item in items:
                price = item.get('price', 0.0)
                quantity = item.get('quantity', 1)
                if quantity > 0:
                    item_total = price * quantity
                    subtotal += item_total
                    item_details.append({
                        'name': item.get('name', 'Unknown'),
                        'total': item_total,
                        'quantity': quantity
                    })
                else:
                    item_details.append({
                        'name': item.get('name', 'Unknown'),
                        'total': 0.0,
                        'quantity': 0
                    })
            return {
                'subtotal': subtotal,
                'items': item_details,
                'item_count': len(item_details)
            }
        """
    ).strip(),
    "ecommerce/discounts.py": dedent(
        """
        def apply_discounts(subtotal, user_tier, coupon_code=None):
            discount_amount = 0.0
            applied_discounts = []
            
            # Tier-based discount
            if user_tier == 'premium':
                tier_discount = subtotal * 0.15
                discount_amount += tier_discount
                applied_discounts.append({'type': 'tier', 'amount': tier_discount})
            elif user_tier == 'gold':
                tier_discount = subtotal * 0.10
                discount_amount += tier_discount
                applied_discounts.append({'type': 'tier', 'amount': tier_discount})
            elif user_tier == 'silver':
                tier_discount = subtotal * 0.05
                discount_amount += tier_discount
                applied_discounts.append({'type': 'tier', 'amount': tier_discount})
            
            # Coupon discount
            if coupon_code:
                if coupon_code == 'SAVE20':
                    coupon_discount = min(subtotal * 0.20, 50.0)
                    discount_amount += coupon_discount
                    applied_discounts.append({'type': 'coupon', 'amount': coupon_discount})
                elif coupon_code == 'SAVE10':
                    coupon_discount = min(subtotal * 0.10, 25.0)
                    discount_amount += coupon_discount
                    applied_discounts.append({'type': 'coupon', 'amount': coupon_discount})
            
            final_amount = max(0.0, subtotal - discount_amount)
            return {
                'original': subtotal,
                'discount': discount_amount,
                'final': final_amount,
                'discounts': applied_discounts
            }
        """
    ).strip(),
    "ecommerce/tax.py": dedent(
        """
        def calculate_tax_and_total(amount, state_code, is_tax_exempt=False):
            if is_tax_exempt:
                return {
                    'subtotal': amount,
                    'tax_rate': 0.0,
                    'tax_amount': 0.0,
                    'total': amount
                }
            
            tax_rates = {
                'CA': 0.0825,
                'NY': 0.08875,
                'TX': 0.0625,
                'FL': 0.06
            }
            
            base_rate = tax_rates.get(state_code, 0.05)
            if amount > 1000:
                luxury_rate = 0.02
                total_rate = base_rate + luxury_rate
            else:
                total_rate = base_rate
            
            tax_amount = amount * total_rate
            total = amount + tax_amount
            
            return {
                'subtotal': amount,
                'tax_rate': total_rate,
                'tax_amount': tax_amount,
                'total': total
            }
        """
    ).strip(),
    "ecommerce/processor.py": dedent(
        """
        from ecommerce.orders import calculate_item_total
        from ecommerce.discounts import apply_discounts
        from ecommerce.tax import calculate_tax_and_total
        
        def process_order(order_data):
            items = order_data.get('items', [])
            user_tier = order_data.get('user_tier', 'standard')
            coupon = order_data.get('coupon_code')
            state = order_data.get('shipping_state', 'CA')
            tax_exempt = order_data.get('tax_exempt', False)
            
            # Step 1: Calculate item totals
            item_result = calculate_item_total(items)
            subtotal = item_result['subtotal']
            
            # Step 2: Apply discounts
            discount_result = apply_discounts(subtotal, user_tier, coupon)
            discounted_amount = discount_result['final']
            
            # Step 3: Calculate tax and final total
            final_result = calculate_tax_and_total(discounted_amount, state, tax_exempt)
            
            return {
                'items': item_result,
                'discounts': discount_result,
                'tax': final_result,
                'order_summary': {
                    'item_count': item_result['item_count'],
                    'original_subtotal': subtotal,
                    'discount_applied': discount_result['discount'],
                    'tax_amount': final_result['tax_amount'],
                    'final_total': final_result['total']
                }
            }
        """
    ).strip(),
}


DUMMY_BASIC_BLOCKS: List[BasicBlock] = [
    # orders.py - calculate_item_total
    BasicBlock(
        block_id="orders:init",
        file_path="ecommerce/orders.py",
        start_line=1,
        end_line=2,
    ),
    BasicBlock(
        block_id="orders:loop_positive",
        file_path="ecommerce/orders.py",
        start_line=3,
        end_line=8,
    ),
    BasicBlock(
        block_id="orders:loop_zero",
        file_path="ecommerce/orders.py",
        start_line=9,
        end_line=13,
    ),
    BasicBlock(
        block_id="orders:return",
        file_path="ecommerce/orders.py",
        start_line=14,
        end_line=17,
    ),
    # discounts.py - apply_discounts
    BasicBlock(
        block_id="discounts:init",
        file_path="ecommerce/discounts.py",
        start_line=1,
        end_line=2,
    ),
    BasicBlock(
        block_id="discounts:premium",
        file_path="ecommerce/discounts.py",
        start_line=4,
        end_line=7,
    ),
    BasicBlock(
        block_id="discounts:gold",
        file_path="ecommerce/discounts.py",
        start_line=8,
        end_line=11,
    ),
    BasicBlock(
        block_id="discounts:silver",
        file_path="ecommerce/discounts.py",
        start_line=12,
        end_line=15,
    ),
    BasicBlock(
        block_id="discounts:coupon_check",
        file_path="ecommerce/discounts.py",
        start_line=17,
        end_line=17,
    ),
    BasicBlock(
        block_id="discounts:save20",
        file_path="ecommerce/discounts.py",
        start_line=18,
        end_line=21,
    ),
    BasicBlock(
        block_id="discounts:save10",
        file_path="ecommerce/discounts.py",
        start_line=22,
        end_line=25,
    ),
    BasicBlock(
        block_id="discounts:final_calc",
        file_path="ecommerce/discounts.py",
        start_line=27,
        end_line=28,
    ),
    BasicBlock(
        block_id="discounts:return",
        file_path="ecommerce/discounts.py",
        start_line=29,
        end_line=34,
    ),
    # tax.py - calculate_tax_and_total
    BasicBlock(
        block_id="tax:exempt_check",
        file_path="ecommerce/tax.py",
        start_line=1,
        end_line=1,
    ),
    BasicBlock(
        block_id="tax:exempt_return",
        file_path="ecommerce/tax.py",
        start_line=2,
        end_line=8,
    ),
    BasicBlock(
        block_id="tax:rates_init",
        file_path="ecommerce/tax.py",
        start_line=10,
        end_line=15,
    ),
    BasicBlock(
        block_id="tax:luxury_check",
        file_path="ecommerce/tax.py",
        start_line=17,
        end_line=17,
    ),
    BasicBlock(
        block_id="tax:luxury_rate",
        file_path="ecommerce/tax.py",
        start_line=18,
        end_line=20,
    ),
    BasicBlock(
        block_id="tax:base_rate",
        file_path="ecommerce/tax.py",
        start_line=21,
        end_line=22,
    ),
    BasicBlock(
        block_id="tax:tax_calc",
        file_path="ecommerce/tax.py",
        start_line=24,
        end_line=25,
    ),
    BasicBlock(
        block_id="tax:return",
        file_path="ecommerce/tax.py",
        start_line=27,
        end_line=32,
    ),
    # processor.py - process_order
    BasicBlock(
        block_id="processor:init",
        file_path="ecommerce/processor.py",
        start_line=6,
        end_line=10,
    ),
    BasicBlock(
        block_id="processor:items_calc",
        file_path="ecommerce/processor.py",
        start_line=12,
        end_line=13,
    ),
    BasicBlock(
        block_id="processor:discounts_apply",
        file_path="ecommerce/processor.py",
        start_line=15,
        end_line=16,
    ),
    BasicBlock(
        block_id="processor:tax_calc",
        file_path="ecommerce/processor.py",
        start_line=18,
        end_line=19,
    ),
    BasicBlock(
        block_id="processor:return",
        file_path="ecommerce/processor.py",
        start_line=21,
        end_line=30,
    ),
]


def get_dummy_sources() -> List[Dict[str, str]]:
    """
    Return sample source files as a list of {file_path, code} dicts.
    """

    return [
        {"file_path": path, "code": source} for path, source in DUMMY_SOURCE_FILES.items()
    ]


def get_dummy_blocks() -> List[BasicBlock]:
    """
    Return the static list of BasicBlock objects used for tracing demos.
    """

    return list(DUMMY_BASIC_BLOCKS)


def get_dummy_exit_lookup() -> Dict[Tuple[str, int], str]:
    """
    Pre-computed (file_path, line) -> block_id mapping for the dummy fixture.
    """

    return build_exit_line_lookup(DUMMY_BASIC_BLOCKS)

